# app/data/repositories.py
from abc import ABC, abstractmethod
from sqlalchemy import select, func

from sqlalchemy.ext.asyncio import AsyncSession
from .models import Usage
import uuid

class IUsageRepository(ABC):
    @abstractmethod
    async def count(self, user_id: str, service: str) -> int: ...
    @abstractmethod
    async def record(self, user_id: str, service: str, paid: bool,
                     tx_id: str | None = None, amount: int | None = None) -> None: ...

class IPaymentRepository(ABC):
    # if you need to store extra payment logs
    pass

class UsageRepository(IUsageRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def count(self, user_id: str, service: str) -> int:
        q = await self.session.execute(
            select(func.count()).where(
                Usage.user_id == user_id, Usage.service == service
            )
        )
        return q.scalar_one()

    async def record(self, user_id: str, service: str, paid: bool,
                     tx_id: str | None = None, amount: int | None = None):
        usage = Usage(
            id=str(uuid.uuid4()),
            user_id=user_id,
            service=service,
            paid=paid,
            transaction_id=tx_id,
            amount=amount
        )
        self.session.add(usage)
        await self.session.commit()
