from typing import Optional

from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_counter import UsageCounter


class UsageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_usage(self, user_id: str, service: str) -> Optional[UsageCounter]:
        stmt = select(UsageCounter).where(
            UsageCounter.user_id == user_id,
            UsageCounter.service == service
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def increment_usage(self, user_id: str, service: str) -> UsageCounter:
        """
        Atomic upsert: If record exists, increment used counter.
        If not, create it.
        """

        # Try update first
        up_stmt = (
            update(UsageCounter)
            .where(
                UsageCounter.user_id == user_id,
                UsageCounter.service == service
            )
            .values(used=UsageCounter.used + 1)
            .returning(UsageCounter)
        )

        result = await self.db.execute(up_stmt)
        row = result.scalar_one_or_none()

        if row:
            await self.db.commit()
            return row

        # Create new row if none exists
        insert_stmt = (
            insert(UsageCounter)
            .values(user_id=user_id, service=service, used=1)
            .returning(UsageCounter)
        )

        result = await self.db.execute(insert_stmt)
        await self.db.commit()
        return result.scalar_one()
