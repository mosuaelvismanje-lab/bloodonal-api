# =========================================================
# FILE: app/services/session_service.py
# =========================================================

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user.user_session import UserSession

# =========================================================
# TOKEN UTILS INTEGRATION
# =========================================================
from app.utils.token_utils import (
    generate_correlation_id,
    stable_uuid,
)

logger = logging.getLogger(__name__)


class SessionService:
    """
    =========================================================
    ENTERPRISE SESSION SERVICE
    =========================================================

    Responsibilities:
    ---------------------------------------------------------
    - Secure session creation
    - Device tracking
    - Refresh token lifecycle
    - Session revocation
    - Activity tracking
    - Audit correlation support
    =========================================================
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =====================================================
    # TIME
    # =====================================================
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # =====================================================
    # CREATE SESSION
    # =====================================================
    async def create_session(
        self,
        *,
        user_id: uuid.UUID,
        refresh_token: str,
        device_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        device_name: Optional[str] = None,
    ) -> UserSession:

        session = UserSession(
            user_id=user_id,
            refresh_token=refresh_token,
            device_id=device_id,
            ip_address=ip_address,
            device_name=device_name,
            last_activity_at=self._now(),
            is_active=True,
        )

        # correlation tracking (enterprise audit)
        if hasattr(session, "correlation_id"):
            session.correlation_id = generate_correlation_id()

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        logger.info(
            "[SESSION_CREATED] user=%s session_id=%s",
            stable_uuid(str(user_id)),
            session.id,
        )

        return session

    # =====================================================
    # GET ACTIVE SESSION
    # =====================================================
    async def get_active_session(
        self,
        refresh_token: str,
    ) -> Optional[UserSession]:

        query = select(UserSession).where(
            UserSession.refresh_token == refresh_token
        )

        result = await self.db.execute(query)
        return result.scalars().first()

    # =====================================================
    # REVOKE SINGLE SESSION
    # =====================================================
    async def revoke_session(
        self,
        session_id: uuid.UUID,
    ) -> bool:

        query = select(UserSession).where(
            UserSession.id == session_id
        )

        result = await self.db.execute(query)
        session = result.scalars().first()

        if not session:
            return False

        session.is_active = False

        if hasattr(session, "revoked_at"):
            session.revoked_at = self._now()

        if hasattr(session, "revocation_correlation_id"):
            session.revocation_correlation_id = (
                generate_correlation_id()
            )

        await self.db.commit()

        logger.info(
            "[SESSION_REVOKED] session_id=%s",
            session_id,
        )

        return True

    # =====================================================
    # REVOKE ALL USER SESSIONS
    # =====================================================
    async def revoke_all_sessions(
        self,
        user_id: uuid.UUID,
    ) -> int:

        query = select(UserSession).where(
            UserSession.user_id == user_id
        )

        result = await self.db.execute(query)
        sessions = result.scalars().all()

        count = 0

        for session in sessions:
            session.is_active = False
            count += 1

            if hasattr(session, "revoked_at"):
                session.revoked_at = self._now()

        await self.db.commit()

        logger.warning(
            "[ALL_SESSIONS_REVOKED] user=%s count=%s",
            stable_uuid(str(user_id)),
            count,
        )

        return count

    # =====================================================
    # UPDATE ACTIVITY
    # =====================================================
    async def update_activity(
        self,
        session_id: uuid.UUID,
    ) -> bool:

        query = select(UserSession).where(
            UserSession.id == session_id
        )

        result = await self.db.execute(query)
        session = result.scalars().first()

        if not session:
            return False

        session.last_activity_at = self._now()

        if hasattr(session, "activity_correlation_id"):
            session.activity_correlation_id = (
                generate_correlation_id()
            )

        await self.db.commit()

        return True

    # =====================================================
    # LIST USER SESSIONS
    # =====================================================
    async def list_user_sessions(
        self,
        user_id: uuid.UUID,
    ) -> list[Dict[str, Any]]:

        query = select(UserSession).where(
            UserSession.user_id == user_id
        )

        result = await self.db.execute(query)
        sessions = result.scalars().all()

        return [
            {
                "id": str(session.id),
                "device_name": session.device_name,
                "device_id": session.device_id,
                "ip_address": session.ip_address,
                "is_active": session.is_active,
                "created_at": session.created_at,
                "last_activity_at": session.last_activity_at,
            }
            for session in sessions
        ]