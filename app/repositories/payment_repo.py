from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment(
        self,
        user_id: str,
        payment_type: str,
        amount: float,
        idempotency_key: Optional[str] = None,
        provider_tx_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Payment:
        payment = Payment(
            user_id=user_id,
            payment_type=payment_type,
            amount=amount,
            idempotency_key=idempotency_key,
            provider_transaction_id=provider_tx_id,
            metadata=metadata or {}
        )
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_by_idempotency(self, idempotency_key: str) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        payment_id: UUID,
        new_status: PaymentStatus,
        provider_tx_id: Optional[str] = None,
    ) -> Optional[Payment]:
        stmt = (
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                status=new_status,
                provider_transaction_id=provider_tx_id
            )
            .returning(Payment)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.scalar_one_or_none()

    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
