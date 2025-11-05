# File: app/repositories/notification_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.notification import Notification

class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def list_for_user(self, user_id: str) -> list[Notification]:
        q = await self._session.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
        return q.scalars().all()

    async def mark_read(self, notification_id: str):
        obj = await self._session.get(Notification, notification_id)
        if obj:
            obj.read = True
            await self._session.commit()
