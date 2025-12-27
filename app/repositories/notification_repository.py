# File: app/repositories/notification_repository.py
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationRepository:
    """
    Repository for handling notifications.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_for_user(self, user_id: str) -> List[Notification]:
        """
        Return all notifications for a given user.
        """
        try:
            result = await self._session.execute(
                select(Notification).where(Notification.user_id == user_id)
            )
            notifications: List[Notification] = result.scalars().all()
            logger.debug("Fetched %d notifications for user_id=%s", len(notifications), user_id)
            return notifications
        except SQLAlchemyError as e:
            logger.exception("Failed to fetch notifications for user_id=%s", user_id)
            raise

    async def mark_read(self, notification_id: str) -> Optional[Notification]:
        """
        Mark a notification as read.
        Returns the updated Notification object or None if not found.
        """
        try:
            notification: Optional[Notification] = await self._session.get(Notification, notification_id)
            if notification:
                notification.read = True
                await self._session.commit()
                logger.debug("Marked notification id=%s as read", notification_id)
            else:
                logger.warning("Notification id=%s not found", notification_id)
            return notification
        except SQLAlchemyError:
            await self._session.rollback()
            logger.exception("Failed to mark notification id=%s as read", notification_id)
            raise
