# app/services/reconciliation_service.py

import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payment import Payment


class ReconciliationService:
    """
    Runs periodically to sync your ledger with provider's ledger.
    """

    @staticmethod
    async def reconcile_payments(db: AsyncSession):
        # Fetch all pending payments
        query = select(Payment).where(Payment.status == "pending")
        result = await db.execute(query)
        pending_payments = result.scalars().all()

        for record in pending_payments:
            provider_status = await ReconciliationService.query_provider(record.provider_tx_id)

            if provider_status != record.status:
                record.status = provider_status
                db.add(record)

        await db.commit()

    @staticmethod
    async def query_provider(provider_tx_id: str) -> str:
        """
        Placeholder: call real provider API to get status.
        """
        await asyncio.sleep(0.1)
        return "success"
