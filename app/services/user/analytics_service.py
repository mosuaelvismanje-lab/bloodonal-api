from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class AnalyticsService:
    """
    Lightweight enterprise analytics layer.

    Handles:
    - event tracking
    - user activity logs
    - system metrics aggregation
    - audit-friendly event storage
    """

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # =========================================================
    # GENERIC EVENT TRACKING
    # =========================================================
    async def track_event(
        self,
        db: AsyncSession,
        *,
        user_id: Optional[uuid.UUID],
        event_name: str,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:

        query = text("""
            INSERT INTO analytics_events (
                id,
                user_id,
                event_name,
                metadata,
                ip_address,
                created_at
            )
            VALUES (
                :id,
                :user_id,
                :event_name,
                :metadata,
                :ip_address,
                :created_at
            )
        """)

        await db.execute(
            query,
            {
                "id": str(uuid.uuid4()),
                "user_id": str(user_id) if user_id else None,
                "event_name": event_name,
                "metadata": metadata or {},
                "ip_address": ip_address,
                "created_at": self._now(),
            },
        )

        await db.commit()

    # =========================================================
    # LOGIN METRICS
    # =========================================================
    async def track_login(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        success: bool,
        ip_address: Optional[str] = None,
    ) -> None:

        await self.track_event(
            db,
            user_id=user_id,
            event_name="login_success" if success else "login_failed",
            metadata={"success": success},
            ip_address=ip_address,
        )

    # =========================================================
    # USER ACTION TRACKING
    # =========================================================
    async def track_user_action(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:

        await self.track_event(
            db,
            user_id=user_id,
            event_name=action,
            metadata=metadata or {},
        )

    # =========================================================
    # BASIC STATS (EXAMPLE)
    # =========================================================
    async def get_event_count(
        self,
        db: AsyncSession,
        event_name: str,
    ) -> int:

        query = text("""
            SELECT COUNT(*)
            FROM analytics_events
            WHERE event_name = :event_name
        """)

        result = await db.execute(query, {"event_name": event_name})
        return result.scalar() or 0


analytics_service = AnalyticsService()