from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.domain.interfaces import IUsageRepository
from app.data.models import Usage

class SQLAlchemyUsageRepository(IUsageRepository):
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def count_uses(self, user_id: str, service: str) -> int:
        result = await self.db_session.execute(
            select(func.count(Usage.id)).where(
                and_(Usage.user_id == user_id, Usage.service == service)
            )
        )
        return result.scalar_one_or_none() or 0

    async def record_usage(
        self,
        user_id: str,
        service: str,
        paid: bool,
        amount: int | None,
        transaction_id: str | None
    ):
        new_usage = Usage(
            user_id=user_id,
            service=service,
            paid=paid,
            amount=amount,
            transaction_id=transaction_id
        )
        self.db_session.add(new_usage)
        await self.db_session.commit()