# app/services/reconciliation_service.py

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Payment
from app.schemas.payment import PaymentResponse
import logging

logger = logging.getLogger(__name__)


class ReconciliationService:
    """
    Periodically reconciles internal payments ledger with external provider.
    """

    @staticmethod
    async def reconcile_payments(db: AsyncSession):
        """
        Check all pending payments and update status from the provider.
        """
        # Fetch all pending payments
        query = select(Payment).where(Payment.status == "pending")
        result = await db.execute(query)
        pending_payments = result.scalars().all()

        if not pending_payments:
            logger.info("No pending payments to reconcile.")
            return

        for record in pending_payments:
            try:
                provider_status = await ReconciliationService.query_provider(record.provider_tx_id)
                if provider_status != record.status:
                    logger.info(
                        "Updating payment %s status from %s to %s",
                        record.internal_tx_id,
                        record.status,
                        provider_status
                    )
                    record.status = provider_status
                    db.add(record)
            except Exception as e:
                logger.error(
                    "Failed to reconcile payment %s: %s",
                    record.internal_tx_id,
                    str(e)
                )

        await db.commit()
        logger.info("Reconciliation completed for %d payment(s).", len(pending_payments))

    @staticmethod
    async def query_provider(provider_tx_id: str) -> str:
        """
        Placeholder for real provider API call.
        Simulates checking the provider ledger for the status of a transaction.

        Returns:
            str: status, e.g., "success", "failed", or "pending"
        """
        await asyncio.sleep(0.1)  # simulate API delay
        # Here you could call an actual provider API
        return "success"

