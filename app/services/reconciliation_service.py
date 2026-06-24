# app/services/reconciliation_service.py

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.domain.interfaces import IPaymentGateway
from app.modules.payment.models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Background reconciliation worker.

    Responsibility:
    - Sync internal DB with external payment provider
    - Fix stuck / pending payments
    - Ensure eventual consistency
    """

    def __init__(self, payment_gateway: IPaymentGateway):
        self.payment_gateway = payment_gateway

    # ======================================================
    # MAIN RECONCILIATION JOB
    # ======================================================
    async def reconcile_payments(self, db: AsyncSession):
        stmt = select(Payment).where(
            Payment.status == PaymentStatus.PENDING
        )

        result = await db.execute(stmt)
        pending_payments = result.scalars().all()

        if not pending_payments:
            logger.info("No pending payments found")
            return

        updated_count = 0

        for payment in pending_payments:
            try:
                provider_status = await self.payment_gateway.verify(
                    payment.provider_tx_id
                )

                # Normalize provider response
                new_status = self._map_status(provider_status)

                if new_status != payment.status:
                    payment.status = new_status
                    db.add(payment)
                    updated_count += 1

                    logger.info(
                        "Reconciled payment %s → %s",
                        payment.id,
                        new_status
                    )

            except Exception as e:
                logger.error(
                    "Reconciliation failed for %s: %s",
                    payment.id,
                    str(e)
                )

        await db.commit()

        logger.info(
            "Reconciliation complete: %d updated",
            updated_count
        )

    # ======================================================
    # STATUS MAPPER
    # ======================================================
    def _map_status(self, provider_status: str) -> PaymentStatus:
        mapping = {
            "success": PaymentStatus.SUCCESS,
            "completed": PaymentStatus.SUCCESS,
            "failed": PaymentStatus.FAILED,
            "pending": PaymentStatus.PENDING,
        }

        return mapping.get(provider_status.lower(), PaymentStatus.PENDING)