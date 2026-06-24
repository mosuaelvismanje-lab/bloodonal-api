from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncGenerator, Callable, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_async_session

logger = logging.getLogger(__name__)

# Allow missing token only for local/debug workflows.
# Production requests should send a valid Bearer token.
security = HTTPBearer(scheme_name="HTTPBearer", auto_error=False)

_DEBUG_UID = uuid.UUID("550e8400-e29b-41d4-a716-446655440000")

# Optional local ORM model import.
# If unavailable, auth still works from Firebase claims.
try:
    from app.models.user import User  # type: ignore
except Exception:  # pragma: no cover
    User = None  # type: ignore


class MockUser:
    def __init__(
        self,
        uid: uuid.UUID,
        email: str | None,
        name: str | None,
        role: str = "user",
        auth_uid: Optional[str] = None,
        is_active: bool = True,
    ):
        self.id = uid
        self.uid = uid
        self.email = email or "unknown@test.com"
        self.name = name or "Unknown User"
        self.role = role
        self.auth_uid = auth_uid or str(uid)
        self.is_active = is_active
        self.is_admin = role.lower() in ["admin", "super_admin", "moderator"]

    @property
    def display_name(self) -> str:
        return self.name or self.email


async def verify_admin_token(
    x_admin_token: str = Header(None, alias="X-Admin-Token"),
):
    if not x_admin_token and not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Admin credentials required")

    if not settings.DEBUG and x_admin_token != settings.ADMIN_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    return x_admin_token or "debug_active"


def require_service_enabled(service_key: str) -> Callable:
    async def _check():
        is_enabled = settings.payment_switches.get(service_key, True)
        if not is_enabled:
            logger.warning("Maintenance mode for: %s", service_key)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The {service_key.replace('_', ' ')} service is offline.",
            )
        return True

    return _check


async def get_current_decoded_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
) -> Dict[str, Any]:
    if credentials is None:
        if settings.DEBUG:
            return {
                "uid": str(_DEBUG_UID),
                "email": "tester@example.com",
                "name": "Emulator Tester",
                "role": "admin",
                "is_admin": True,
                "email_verified": True,
            }

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    token = credentials.credentials.strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )

    try:
        from firebase_admin import auth as firebase_auth  # type: ignore
    except Exception as exc:
        logger.exception("Firebase auth library unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc

    try:
        decoded_token = firebase_auth.verify_id_token(token)
        if not isinstance(decoded_token, dict):
            raise ValueError("Invalid token payload")

        if decoded_token.get("uid") is None and decoded_token.get("sub") is None:
            raise ValueError("Invalid Firebase token payload")

        return decoded_token
    except Exception as exc:
        logger.warning("Invalid or expired Firebase token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    decoded_token: Dict[str, Any] = Depends(get_current_decoded_token),
    db: AsyncSession = Depends(lambda: get_db()),
) -> MockUser:
    raw_uid = (
        decoded_token.get("app_uid")
        or decoded_token.get("uid")
        or decoded_token.get("sub")
    )

    if not raw_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user id",
        )

    email = str(decoded_token.get("email", "unknown@test.com")).strip()
    name = str(decoded_token.get("name", "Test User")).strip()

    role = str(decoded_token.get("role") or "user").lower()
    if decoded_token.get("admin") is True or decoded_token.get("is_admin") is True:
        role = "admin"

    try:
        user_uuid = uuid.UUID(str(raw_uid))
    except Exception:
        namespace = uuid.uuid5(
            uuid.NAMESPACE_DNS,
            getattr(settings, "PROJECT_NAME", "bloodonal"),
        )
        user_uuid = uuid.uuid5(namespace, str(raw_uid))

    # ---------------------------------------------------------
    # Database-aware user hydration
    # ---------------------------------------------------------
    if User is not None:
        try:
            query = select(User)

            if hasattr(User, "auth_uid"):
                query = query.where(User.auth_uid == str(raw_uid))
            elif hasattr(User, "email"):
                query = query.where(User.email == email.lower())

            if hasattr(User, "deleted_at"):
                query = query.where(User.deleted_at.is_(None))

            result = await db.execute(query)
            user_record = result.scalar_one_or_none()

            if user_record is not None:
                if hasattr(user_record, "is_active") and not user_record.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Account disabled",
                    )

                return MockUser(
                    uid=getattr(user_record, "uid", user_uuid),
                    email=getattr(user_record, "email", email),
                    name=getattr(user_record, "name", name),
                    role=getattr(user_record, "role", role),
                    auth_uid=str(raw_uid),
                    is_active=getattr(user_record, "is_active", True),
                )

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("User lookup failed: %s", exc)

    return MockUser(
        uid=user_uuid,
        email=email,
        name=name,
        role=role,
        auth_uid=str(raw_uid),
        is_active=True,
    )


async def get_admin_user(
    current_user: MockUser = Depends(get_current_user),
) -> MockUser:
    if not current_user.is_admin:
        logger.warning("Unauthorized admin attempt: %s", current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )
    return current_user


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        try:
            yield session
        except Exception as e:
            logger.exception("DB session error: %s", e)
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_redis(request: Request):
    redis_client = getattr(request.app.state, "redis", None)

    if redis_client is None:
        logger.error("Redis not initialized in app.state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service not available",
        )

    return redis_client


async def get_request_id(
    x_request_id: Optional[str] = Header(default=None, alias="X-Request-ID"),
) -> str:
    return x_request_id or str(uuid.uuid4())


def get_current_user_id(user: MockUser = Depends(get_current_user)) -> uuid.UUID:
    return user.uid


get_db_session = get_db