# app/services/payment_service.py

import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_free_usage_count, increment_usage_count
from app.models.payment import Payment
from app.schemas.payment import PaymentRequest, PaymentResponse

FREE_LIMITS = {
    "doctor": 5,
    "nurse": 3,
    "biker": 2,
    "taxi": 2,
    "blood_request": 10,
}

BASE_FEE = {
    "doctor": 300,
    "nurse": 200,
    "biker": 100,
    "taxi": 150,
    "blood_request": 0,  # dynamic — can be changed later
}


class PaymentService:
    """
    Main orchestrator for ALL payments
    """

    @staticmethod
    async def get_remaining_free_uses(db: AsyncSession, user_id: str, category: str) -> int:
        used = await get_free_usage_count(db, user_id, category)
        limit = FREE_LIMITS.get(category, 0)
        return max(limit - used, 0)

    @staticmethod
    async def generate_transaction_id(category: str) -> str:
        return f"{category}-{uuid.uuid4().hex}"

    @staticmethod
    async def charge_provider_gateway(amount: float, metadata: dict) -> str:
        """
        Stub: simulate charging an external gateway
        """
        await asyncio.sleep(0.1)  # simulate api delay
        return "provider_tx_" + uuid.uuid4().hex

    @staticmethod
    async def process_payment(
            db: AsyncSession,
            user_id: str,
            category: str,
            req: PaymentRequest,
    ) -> PaymentResponse:
        """
        Core payment flow:
        - Check free usage
        - Decide amount
        - Create internal ledger
        - Submit provider payment if needed
        - Return transaction info
        """

        # Determine free uses
        free_left = await PaymentService.get_remaining_free_uses(db, user_id, category)

        if free_left > 0:
            amount = 0
        else:
            amount = req.amount or BASE_FEE.get(category, 0)

        # Internal transaction ID
        tx_id = await PaymentService.generate_transaction_id(category)

        # Provider transaction (if paid)
        provider_tx = None
        if amount > 0:
            provider_tx = await PaymentService.charge_provider_gateway(amount, req.metadata)

        # Write ledger
        payment_entry = Payment(
            user_id=user_id,
            category=category,
            amount=amount,
            internal_tx_id=tx_id,
            provider_tx_id=provider_tx,
            status="success",
            metadata=req.metadata,
            created_at=datetime.utcnow(),
        )
        db.add(payment_entry)

        # Increment free usage if free
        if amount == 0:
            await increment_usage_count(db, user_id, category)

        await db.commit()

        return PaymentResponse(
            success=True,
            transaction_id=tx_id,
            status="success",
            provider_redirect_url=None,
            message="Payment processed successfully",
        )
