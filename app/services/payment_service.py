# app/services/payment_service.py

import asyncio
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_free_usage_count, increment_usage_count
from app.models.payment import Payment
from app.schemas.payment import PaymentRequest, PaymentResponse

# -------------------------
# Configuration
# -------------------------
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
    "blood_request": 0,
}

# Category-specific fees for routers
DOCTOR_FEE = BASE_FEE["doctor"]
NURSE_FEE = BASE_FEE["nurse"]
BIKE_FEE = BASE_FEE["biker"]
TAXI_FEE = BASE_FEE["taxi"]
BLOOD_REQUEST_FEE = BASE_FEE["blood_request"]


class PaymentService:
    """
    Main orchestrator for all payments.
    Provides:
      • Free usage check
      • Internal transaction generation
      • Optional external provider charging
      • Ledger recording
    """

    @staticmethod
    async def get_remaining_free_uses(
        db: AsyncSession, user_id: str, category: str
    ) -> int:
        """
        Returns how many free uses a user has left for a given category.
        """
        used = await get_free_usage_count(db, user_id, category)
        limit = FREE_LIMITS.get(category, 0)
        return max(limit - used, 0)

    @staticmethod
    async def generate_transaction_id(category: str) -> str:
        """
        Generates a unique internal transaction ID.
        """
        return f"{category}-{uuid.uuid4().hex}"

    @staticmethod
    async def charge_provider_gateway(amount: float, metadata: Optional[dict] = None) -> str:
        """
        Stub: Simulate charging an external provider.
        """
        await asyncio.sleep(0.1)  # simulate API delay
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
          1. Check free usage
          2. Determine amount to charge
          3. Generate internal transaction ID
          4. Charge external provider if needed
          5. Write to internal ledger
          6. Increment usage count for free actions
        """
        # Step 1: check free usage
        free_left = await PaymentService.get_remaining_free_uses(db, user_id, category)

        # Step 2: determine amount
        amount = 0 if free_left > 0 else (req.amount or BASE_FEE.get(category, 0))

        # Step 3: internal transaction ID
        tx_id = await PaymentService.generate_transaction_id(category)

        # Step 4: provider transaction if paid
        provider_tx = None
        if amount > 0:
            provider_tx = await PaymentService.charge_provider_gateway(amount, req.metadata)

        # Step 5: create ledger entry
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

        # Step 6: increment usage if free
        if amount == 0:
            await increment_usage_count(db, user_id, category)

        # Commit transaction
        await db.commit()

        # Return unified payment response
        return PaymentResponse(
            success=True,
            transaction_id=tx_id,
            status="success",
            provider_redirect_url=None,
            message="Payment processed successfully",
        )


# -------------------------
# Convenience aliases for routers
# -------------------------
get_remaining_free_count = PaymentService.get_remaining_free_uses
record_payment = PaymentService.process_payment
