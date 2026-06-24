# =========================================================
# FILE: app/services/user/security_service.py
# =========================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user.user_security import UserSecurity

# =========================================================
# TOKEN UTILS INTEGRATION
# =========================================================
from app.utils.token_utils import (
    generate_correlation_id,
    stable_uuid,
)

logger = logging.getLogger(__name__)


class SecurityService:
    """
    =========================================================
    ENTERPRISE SECURITY SERVICE
    =========================================================

    Responsibilities:
    ---------------------------------------------------------
    - Login attempt tracking
    - Account locking/unlocking
    - MFA state management
    - Compromise detection
    - Security audit readiness
    - Correlation tracking support
    =========================================================
    """

    MAX_FAILED_ATTEMPTS = 5
    LOCK_DURATION_MINUTES = 15

    # =========================================================
    # TIME
    # =========================================================
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # =========================================================
    # FETCH SECURITY RECORD
    # =========================================================
    async def get_security(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> Optional[UserSecurity]:

        stmt = select(UserSecurity).where(
            UserSecurity.user_id == user_id
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================
    # ENSURE SECURITY ROW EXISTS
    # =========================================================
    async def ensure_security_row(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> UserSecurity:

        security = await self.get_security(db, user_id)

        if security:
            return security

        security = UserSecurity(
            id=uuid.uuid4(),
            user_id=user_id,
            created_at=self._now(),
            updated_at=self._now(),
        )

        db.add(security)
        await db.commit()
        await db.refresh(security)

        logger.info(
            "[SECURITY_CREATED] user_id=%s correlation_id=%s",
            user_id,
            generate_correlation_id(),
        )

        return security

    # =========================================================
    # LOGIN SUCCESS
    # =========================================================
    async def record_success_login(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> None:

        security = await self.ensure_security_row(db, user_id)

        security.record_successful_login()

        # reset security state
        security.is_locked = False
        security.lock_reason = None
        security.locked_until = None

        # stable audit tracking (token_utils usage)
        if hasattr(security, "last_success_correlation_id"):
            security.last_success_correlation_id = (
                generate_correlation_id()
            )

        security.updated_at = self._now()

        await db.commit()

        logger.info(
            "[LOGIN_SUCCESS] user=%s",
            stable_uuid(str(user_id)),
        )

    # =========================================================
    # LOGIN FAILURE
    # =========================================================
    async def record_failed_login(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> None:

        security = await self.ensure_security_row(db, user_id)

        security.record_failed_login()

        if (
            security.failed_login_attempts
            >= self.MAX_FAILED_ATTEMPTS
        ):
            security.lock_account(
                reason="Too many failed login attempts",
                until=self._now()
                + timedelta(
                    minutes=self.LOCK_DURATION_MINUTES
                ),
            )

            logger.warning(
                "[ACCOUNT_LOCKED] user=%s attempts=%s",
                stable_uuid(str(user_id)),
                security.failed_login_attempts,
            )

        security.updated_at = self._now()

        await db.commit()

    # =========================================================
    # ACCOUNT LOCK CHECK
    # =========================================================
    async def is_account_locked(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> bool:

        security = await self.get_security(db, user_id)

        if not security:
            return False

        if not security.is_locked:
            return False

        # auto-unlock expired lock
        if (
            security.locked_until
            and security.locked_until < self._now()
        ):
            security.unlock_account()
            security.updated_at = self._now()
            await db.commit()

            logger.info(
                "[ACCOUNT_AUTO_UNLOCK] user=%s",
                stable_uuid(str(user_id)),
            )

            return False

        return True

    # =========================================================
    # COMPROMISE FLAGGING
    # =========================================================
    async def mark_compromised(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        note: Optional[str] = None,
    ) -> None:

        security = await self.ensure_security_row(db, user_id)

        security.mark_compromised(note)

        if hasattr(security, "compromise_correlation_id"):
            security.compromise_correlation_id = (
                generate_correlation_id()
            )

        security.updated_at = self._now()

        await db.commit()

        logger.critical(
            "[ACCOUNT_COMPROMISED] user=%s note=%s",
            stable_uuid(str(user_id)),
            note,
        )

    # =========================================================
    # MFA CONTROL
    # =========================================================
    async def enable_mfa(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        method: str,
    ) -> None:

        security = await self.ensure_security_row(db, user_id)

        security.enable_mfa(method)

        if hasattr(security, "mfa_enabled_at"):
            security.mfa_enabled_at = self._now()

        security.updated_at = self._now()

        await db.commit()

        logger.info(
            "[MFA_ENABLED] user=%s method=%s",
            stable_uuid(str(user_id)),
            method,
        )

    async def disable_mfa(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> None:

        security = await self.ensure_security_row(db, user_id)

        security.disable_mfa()

        if hasattr(security, "mfa_disabled_at"):
            security.mfa_disabled_at = self._now()

        security.updated_at = self._now()

        await db.commit()

        logger.info(
            "[MFA_DISABLED] user=%s",
            stable_uuid(str(user_id)),
        )


# =========================================================
# SINGLETON
# =========================================================
security_service = SecurityService()