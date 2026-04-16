import logging
from typing import Optional, Dict, Any
from uuid import UUID

# ✅ Added 'func' to the main sqlalchemy import
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

# ✅ Using the unified model we established
from app.models.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)

class PaymentRepository:
    """
    Repository for managing financial records and state transitions.
    Ensures that payments move strictly through PENDING -> SUCCESS/FAILED.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_payment(
            self,
            user_id: UUID,
            payment_type: str,
            amount: float,
            idempotency_key: Optional[str] = None,
            provider_tx_id: Optional[str] = None,
            details: Optional[Dict[str, Any]] = None,
    ) -> Payment:
        """
        Registers a new transaction.
        Uses idempotency_key to prevent double-charging on network retries.
        """
        payment = Payment(
            user_id=user_id,
            payment_type=payment_type,
            amount=amount,
            status=PaymentStatus.PENDING,
            idempotency_key=idempotency_key,
            provider_transaction_id=provider_tx_id,
            metadata=details or {}
        )

        try:
            self.db.add(payment)
            # Use flush to keep the transaction open for the Orchestrator
            await self.db.flush()
            return payment
        except IntegrityError:
            await self.db.rollback()
            logger.warning(f"💳 Duplicate payment attempt blocked: {idempotency_key}")
            raise ValueError("This transaction has already been initiated.")

    async def update_status(
            self,
            payment_id: UUID,
            new_status: PaymentStatus,
            provider_tx_id: Optional[str] = None,
    ) -> Optional[Payment]:
        """
        State Machine Guard: Atomic update that prevents altering terminal transactions.
        If a payment is already SUCCESS, it cannot be changed back to FAILED or PENDING.
        """
        # Terminal states are immutable
        terminal_states = [PaymentStatus.SUCCESS, PaymentStatus.FAILED]

        stmt = (
            update(Payment)
            .where(Payment.id == payment_id)
            .where(Payment.status.notin_(terminal_states))
            .values(
                status=new_status,
                provider_transaction_id=provider_tx_id or Payment.provider_transaction_id,
                # ✅ func.now() ensures the DB timestamp is used
                updated_at=func.now()
            )
            .returning(Payment)
        )

        result = await self.db.execute(stmt)
        updated_payment = result.scalar_one_or_none()

        if updated_payment:
            logger.info(f"✅ Payment {payment_id} transitioned to {new_status}")
            return updated_payment

        logger.info(f"⚠️ Update skipped for {payment_id}: Payment is already finalized or missing.")
        return None

    async def get_by_provider_ref(self, reference: str) -> Optional[Payment]:
        """Essential for Webhook processing from mobile money providers (MTN/Orange)."""
        stmt = select(Payment).where(Payment.provider_transaction_id == reference)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_idempotency(self, key: str) -> Optional[Payment]:
        """Checks if a request has already created a payment record."""
        stmt = select(Payment).where(Payment.idempotency_key == key)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_payment_by_id(self, payment_id: UUID) -> Optional[Payment]:
        """Standard Primary Key lookup."""
        return await self.db.get(Payment, payment_id)