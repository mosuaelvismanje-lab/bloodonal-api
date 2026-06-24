from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from app.models.user.user_security import UserSecurity

logger = logging.getLogger(__name__)


class SecurityRepositoryError(Exception):
    pass


class SecurityRepository:
    """
    =========================================================
    SECURITY REPOSITORY (ENTERPRISE GRADE)
    =========================================================
    Handles:
    - login failure tracking
    - account lock/unlock
    - MFA state
    - suspicious activity
    - compromise handling
    =========================================================
    """

    # =====================================================
    # GET SECURITY ROW
    # =====================================================
    async def get(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> Optional[UserSecurity]:
        result = await db.execute(
            UserSecurity.__table__.select().where(
                UserSecurity.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    # =====================================================
    # RECORD SUCCESS LOGIN
    # =====================================================
    async def record_success_login(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> UserSecurity:
        try:
            sec = await self.get(db, user_id=user_id)
            if not sec:
                sec = UserSecurity(user_id=user_id)
                db.add(sec)

            sec.record_successful_login()
            sec.last_login_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(sec)
            return sec

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Security login success failed")
            raise SecurityRepositoryError("Failed security update") from exc

    # =====================================================
    # RECORD FAILED LOGIN
    # =====================================================
    async def record_failed_login(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> UserSecurity:
        try:
            sec = await self.get(db, user_id=user_id)
            if not sec:
                sec = UserSecurity(user_id=user_id)
                db.add(sec)

            sec.record_failed_login()

            # auto lock threshold
            if sec.failed_login_attempts >= 5:
                sec.lock_account(
                    reason="Too many failed login attempts",
                    until=datetime.now(timezone.utc) + timedelta(minutes=15),
                )

            await db.commit()
            await db.refresh(sec)
            return sec

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Security login failure tracking failed")
            raise SecurityRepositoryError("Failed security update") from exc

    # =====================================================
    # UNLOCK ACCOUNT
    # =====================================================
    async def unlock(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> UserSecurity:
        sec = await self.get(db, user_id=user_id)

        if not sec:
            raise HTTPException(status_code=404, detail="Security record not found")

        sec.unlock_account()

        await db.commit()
        await db.refresh(sec)
        return sec

    # =====================================================
    # MARK COMPROMISED
    # =====================================================
    async def mark_compromised(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        note: Optional[str] = None,
    ) -> UserSecurity:
        sec = await self.get(db, user_id=user_id)

        if not sec:
            raise HTTPException(status_code=404, detail="Security record not found")

        sec.mark_compromised(note)

        await db.commit()
        await db.refresh(sec)
        return sec


security_repository = SecurityRepository()