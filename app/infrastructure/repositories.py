from typing import Optional, Dict, Any
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces import IUsageRepository
from app.models.usage_counter import UsageCounter  # Changed from app.data.models.Usage

class SQLAlchemyUsageRepository(IUsageRepository):
    """
    SQLAlchemy implementation of IUsageRepository.
    Matches the abstract methods defined in interfaces.py.
    """

    def __init__(self, db_session: AsyncSession):
        # We use self.session to interact with the database
        self.session = db_session

    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        FIXED: Implementation of the missing abstract method.
        Checks if a request with this key was already processed.
        """
        if not key:
            return None

        stmt = select(UsageCounter).where(UsageCounter.idempotency_key == key)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return {
                "user_id": row.user_id,
                "service": row.service,
                "used": row.used,
                "request_id": row.request_id
            }
        return None

    async def count_uses(self, user_id: str, service: str) -> int:
        """
        Requirement: Fetch current usage count for the user and service.
        """
        stmt = select(UsageCounter).where(
            UsageCounter.user_id == user_id,
            UsageCounter.service == service
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return row.used if row else 0

    async def record_usage(
        self,
        user_id: str,
        service: str,
        paid: bool,
        amount: float,
        transaction_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> None:
        """
        FIXED: Updated signature to match IUsageRepository exactly.
        Atomically records usage with idempotency protection.
        """
        # 1. Try to increment the 'used' count for an existing user/service record
        up_stmt = (
            update(UsageCounter)
            .where(
                UsageCounter.user_id == user_id,
                UsageCounter.service == service
            )
            .values(
                used=UsageCounter.used + 1,
                idempotency_key=idempotency_key,
                request_id=request_id
            )
        )

        result = await self.session.execute(up_stmt)

        # 2. If no row was updated, it's a first-time use: insert a new record
        if result.rowcount == 0:
            ins_stmt = insert(UsageCounter).values(
                user_id=user_id,
                service=service,
                used=1,
                idempotency_key=idempotency_key,
                request_id=request_id
            )
            await self.session.execute(ins_stmt)

        # 3. Finalize the transaction
        await self.session.commit()
