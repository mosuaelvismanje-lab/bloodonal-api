import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.exc import SQLAlchemyError

# ✅ Points to your unified Notification model
from app.models.notification import Notification

logger = logging.getLogger(__name__)

class NotificationRepository:
    """
    Handles persistence for in-app alerts.
    Standardized for UUID lookups and 2026 Modular Service events.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ---------------------------------------------------------
    # ✅ Create Notification
    # ---------------------------------------------------------
    async def create_notification(
            self,
            user_id: uuid.UUID,
            sub_type: str,
            message: str,
            title: Optional[str] = None,
            location: Optional[str] = None,
            phone: Optional[str] = None,
    ) -> Notification:
        """
        Persists a new notification.
        Used for: 'blood-request-nearby', 'payment-success', 'donor-accepted'.
        """
        try:
            new_notif = Notification(
                id=uuid.uuid4(),
                user_id=user_id,
                title=title,
                sub_type=sub_type,
                location=location,
                phone=phone,
                message=message,
                # ✅ Postgres handles the timezone-aware comparison better this way
                created_at=datetime.now(timezone.utc),
                is_read=False
            )
            self.session.add(new_notif)
            # We use flush() if this is part of a larger transaction (like activation)
            # Or commit() if it's a standalone alert.
            await self.session.flush()

            logger.info(f"🔔 Notification created for user {user_id}: {sub_type}")
            return new_notif
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Failed to persist notification for {user_id}: {e}")
            raise

    # ---------------------------------------------------------
    # ✅ List for User (Optimized)
    # ---------------------------------------------------------
    async def list_for_user(self, user_id: uuid.UUID, limit: int = 50) -> List[Notification]:
        """
        Fetch the latest in-app alerts for a user's notification bell.
        """
        try:
            stmt = (
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(desc(Notification.created_at))
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error fetching notifications for {user_id}: {e}")
            return []

    # ---------------------------------------------------------
    # ✅ Mark Read
    # ---------------------------------------------------------
    async def mark_read(self, notification_id: uuid.UUID) -> bool:
        """
        Updates the read status. Returns True if successful.
        """
        try:
            notif = await self.session.get(Notification, notification_id)
            if notif:
                notif.is_read = True
                await self.session.flush()
                return True
            return False
        except SQLAlchemyError:
            await self.session.rollback()
            return False