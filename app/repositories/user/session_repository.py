from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status

from app.models.user.user_session import UserSession  # assumed model

logger = logging.getLogger(__name__)


class SessionRepositoryError(Exception):
    pass


class SessionRepository:
    """
    =========================================================
    SESSION REPOSITORY (ENTERPRISE)
    =========================================================
    Handles:
    - login sessions
    - refresh token tracking
    - device sessions
    - logout / revoke
    - session validity checks
    =========================================================
    """

    # =====================================================
    # CREATE SESSION
    # =====================================================
    async def create_session(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        refresh_token: str,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSession:
        try:
            session = UserSession(
                user_id=user_id,
                refresh_token=refresh_token,
                device_id=device_id,
                ip_address=ip_address,
                user_agent=user_agent,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                last_active_at=datetime.now(timezone.utc),
            )

            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Session creation failed")
            raise SessionRepositoryError("Failed to create session") from exc

    # =====================================================
    # GET ACTIVE SESSION
    # =====================================================
    async def get_by_token(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> Optional[UserSession]:
        try:
            stmt = select(UserSession).where(
                and_(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active.is_(True),
                )
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none()

        except SQLAlchemyError as exc:
            logger.exception("Session lookup failed")
            raise SessionRepositoryError("Failed to fetch session") from exc

    # =====================================================
    # REVOKE SESSION
    # =====================================================
    async def revoke_session(
        self,
        db: AsyncSession,
        *,
        refresh_token: str,
    ) -> bool:
        try:
            session = await self.get_by_token(db, refresh_token=refresh_token)

            if not session:
                return False

            session.is_active = False
            session.revoked_at = datetime.now(timezone.utc)

            await db.commit()
            return True

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Session revoke failed")
            raise SessionRepositoryError("Failed to revoke session") from exc

    # =====================================================
    # USER SESSIONS
    # =====================================================
    async def get_user_sessions(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        active_only: bool = True,
    ) -> List[UserSession]:
        stmt = select(UserSession).where(UserSession.user_id == user_id)

        if active_only:
            stmt = stmt.where(UserSession.is_active.is_(True))

        result = await db.execute(stmt)
        return list(result.scalars().all())


session_repository = SessionRepository()