# =========================================================
# FILE: app/services/user/auth_service.py
# =========================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper.user_mapper import user_mapper
from app.repositories.notification_repository import notification_repository
from app.repositories.user.security_repository import security_repository
from app.repositories.user.session_repository import session_repository
from app.repositories.user.user_repository import user_repository
from app.services.user.analytics_service import analytics_service

from app.validators.auth_validator import AuthValidator
from app.validators.security_validator import security_validator
from app.validators.user_validator import UserValidator

# ✅ NEW IMPORT (token utilities integration)
from app.utils.token_utils import (
    generate_token,
    generate_correlation_id,
    stable_uuid,
    generate_numeric_otp,
)

logger = logging.getLogger(__name__)


# =========================================================
# EXCEPTIONS
# =========================================================
class AuthServiceError(Exception):
    pass


class AuthenticationFailedError(AuthServiceError):
    pass


class SessionCreationError(AuthServiceError):
    pass


# =========================================================
# AUTH SERVICE
# =========================================================
class AuthService:
    """
    Enterprise Authentication Service
    """

    # =====================================================
    # LOGIN / ACCOUNT SYNC
    # =====================================================
    async def login_user(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        email: str,
        name: str,
        device_id: Optional[str] = None,
        platform: Optional[str] = None,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
        refresh_token: Optional[str] = None,
        ip_address: Optional[str] = None,
        fcm_token: Optional[str] = None,
    ) -> Dict[str, Any]:

        try:
            # =================================================
            # CORRELATION ID (FOR LOG TRACKING)
            # =================================================
            correlation_id = generate_correlation_id()

            # =================================================
            # VALIDATION
            # =================================================
            auth_uid = auth_uid.strip()

            email = AuthValidator.validate_email(email)
            name = UserValidator.validate_full_name(name)

            device_id = device_id.strip() if device_id else None
            platform = platform.strip() if platform else None

            # =================================================
            # STABLE INTERNAL USER ID (OPTIONAL USE CASE)
            # =================================================
            internal_ref = stable_uuid(auth_uid)

            # =================================================
            # UPSERT USER
            # =================================================
            user, created = await user_repository.upsert_from_firebase(
                db,
                auth_uid=auth_uid,
                email=email,
                name=name,
                platform=platform,
                device_id=device_id,
                device_model=device_model,
                app_version=app_version,
            )

            logger.info(
                "[AUTH_USER_SYNC] cid=%s auth_uid=%s created=%s",
                correlation_id,
                auth_uid,
                created,
            )

            # =================================================
            # SECURITY LOG
            # =================================================
            await security_repository.record_success_login(
                db,
                user_id=str(user.uid),
            )

            # =================================================
            # SESSION CREATION
            # =================================================
            session = None

            if refresh_token:

                # OPTIONAL: generate session token if missing
                if not refresh_token:
                    refresh_token = generate_token()

                session = await session_repository.create_session(
                    db,
                    user_id=str(user.uid),
                    refresh_token=refresh_token,
                    device_id=device_id,
                    ip_address=ip_address,
                    user_agent=platform,
                )

                if not session:
                    raise SessionCreationError("Failed to create session")

            # =================================================
            # LOGIN TRACKING
            # =================================================
            await user_repository.mark_login(
                db,
                auth_uid=auth_uid,
                ip_address=ip_address,
                device_id=device_id,
                device_model=device_model,
                app_version=app_version,
            )

            # =================================================
            # OPTIONAL FCM TOKEN
            # =================================================
            if fcm_token:
                try:
                    await notification_repository.register_device_token(
                        db,
                        user_id=str(user.uid),
                        token=fcm_token,
                        platform=platform,
                        device_id=device_id,
                    )
                except Exception as exc:
                    logger.warning("[FCM_REGISTER_FAIL] %s", exc)

            # =================================================
            # ANALYTICS EVENT
            # =================================================
            try:
                await analytics_service.track_event(
                    db=db,
                    user_id=user.uid,
                    event_name="user_login",
                    metadata={
                        "platform": platform,
                        "device_id": device_id,
                        "app_version": app_version,
                        "created": created,
                        "correlation_id": correlation_id,
                        "internal_ref": str(internal_ref),
                    },
                )
            except Exception as exc:
                logger.warning("[AUTH_ANALYTICS_FAIL] %s", exc)

            # =================================================
            # RESPONSE
            # =================================================
            return {
                "success": True,
                "user": user_mapper.to_user_response(user),
                "created": created,
                "session": session,
                "correlation_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except ValueError as exc:
            raise AuthenticationFailedError(str(exc)) from exc

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("[AUTH_DATABASE_ERROR]")
            raise AuthServiceError("Database authentication error") from exc

        except SessionCreationError:
            await db.rollback()
            raise

        except Exception as exc:
            await db.rollback()
            logger.exception("[AUTH_LOGIN_FAILED]")
            raise AuthServiceError("Login failed") from exc

    # =====================================================
    # LOGOUT
    # =====================================================
    async def logout_user(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> bool:

        try:
            refresh_token = refresh_token.strip()

            if not refresh_token:
                raise AuthServiceError("Refresh token required")

            return await session_repository.revoke_session(
                db,
                refresh_token=refresh_token,
            )

        except Exception as exc:
            logger.exception("[AUTH_LOGOUT_FAILED]")
            raise AuthServiceError("Logout failed") from exc

    # =====================================================
    # REVOKE ALL SESSIONS
    # =====================================================
    async def revoke_all_sessions(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> Dict[str, Any]:

        try:
            revoked_count = await session_repository.revoke_all_sessions(
                db,
                user_id=user_id,
            )

            return {
                "success": True,
                "revoked_sessions": revoked_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            logger.exception("[AUTH_REVOKE_ALL_FAILED]")
            raise AuthServiceError("Failed to revoke sessions") from exc

    # =====================================================
    # VALIDATE SESSION
    # =====================================================
    async def validate_session(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> bool:

        try:
            session = await session_repository.get_active_session(
                db,
                refresh_token=refresh_token,
            )
            return session is not None

        except Exception:
            logger.exception("[SESSION_VALIDATION_FAILED]")
            return False

    # =====================================================
    # DEVICE TOKEN
    # =====================================================
    async def register_device_token(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        token: str,
        platform: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> bool:

        try:
            token = token.strip()

            if not token:
                return False

            await notification_repository.register_device_token(
                db,
                user_id=user_id,
                token=token,
                platform=platform,
                device_id=device_id,
            )

            return True

        except Exception:
            logger.exception("[FCM_REGISTER_ERROR]")
            return False

    # =====================================================
    # HEALTH CHECK
    # =====================================================
    async def health_check(self) -> Dict[str, Any]:

        return {
            "service": "auth_service",
            "status": "healthy",
            "time": datetime.now(timezone.utc).isoformat(),
        }


auth_service = AuthService()