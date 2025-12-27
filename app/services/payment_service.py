import asyncio
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Union, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_free_usage_count, increment_usage_count
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentResponse


# ======================================================
# CONFIGURATION
# ======================================================

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

PAYMENT_GATEWAYS = {
    "MTN": {
        "business_number": "676657577",
        "ussd": "*126*2*{receiver}*{amount}#",
    },
    "ORANGE": {
        "business_number": "690112233",
        "ussd": "#150*1*1*{receiver}*{amount}#",
    },
}

PAYMENT_TIMEOUT_MINUTES = 10


# ======================================================
# HELPERS (SECURITY / USSD)
# ======================================================

def generate_reference() -> str:
    return str(uuid.uuid4())


def generate_signature(reference: str, amount: float, phone: str) -> str:
    raw = f"{reference}:{amount}:{phone}"
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_ussd(gateway: str, amount: float) -> str:
    gateway = gateway.upper()
    config = PAYMENT_GATEWAYS[gateway]
    return config["ussd"].format(
        receiver=config["business_number"],
        amount=int(amount),
    )


# ======================================================
# PAYMENT SERVICE
# ======================================================

class PaymentService:
    """
    Unified payment service supporting:
    • Free usage
    • Paid USSD (MTN / ORANGE)
    • Anti-tampering
    • Reference tracking
    • Manual confirmation
    """

    # -------------------------
    # Free usage
    # -------------------------
    @staticmethod
    async def get_remaining_free_uses(
        db: AsyncSession,
        user_id: str,
        category: str,
    ) -> int:
        used = await get_free_usage_count(db, user_id, category)
        limit = FREE_LIMITS.get(category, 0)
        return max(limit - used, 0)

    # -------------------------
    # Core payment flow
    # -------------------------
    @staticmethod
    async def process_payment(
        db: AsyncSession,
        *,
        user_id: str,
        user_phone: str,
        category: str,
        gateway: Optional[str],
        req_data: Union[Dict, object],
    ) -> PaymentResponse:
        """
        Returns:
        • FREE → immediate success
        • PAID → reference + USSD code
        """

        # Extract metadata / amount
        metadata = (
            getattr(req_data, "metadata", None)
            if not isinstance(req_data, dict)
            else req_data.get("metadata")
        )

        amount = (
            getattr(req_data, "amount", None)
            if not isinstance(req_data, dict)
            else req_data.get("amount")
        )

        # Step 1: free usage check
        free_left = await PaymentService.get_remaining_free_uses(
            db, user_id, category
        )

        # Step 2: determine payable amount
        final_amount = 0 if free_left > 0 else (amount or BASE_FEE.get(category, 0))

        # -------------------------
        # FREE FLOW
        # -------------------------
        if final_amount == 0:
            await increment_usage_count(db, user_id, category)

            return PaymentResponse(
                success=True,
                status="FREE",
                message="Free usage applied",
                transaction_id=None,
                ussd_code=None,
            )

        # -------------------------
        # PAID FLOW (USSD)
        # -------------------------
        gateway = gateway.upper()
        reference = generate_reference()
        signature = generate_signature(reference, final_amount, user_phone)

        ussd_code = generate_ussd(gateway, final_amount)

        payment = Payment(
            reference=reference,
            user_id=user_id,
            user_phone=user_phone,
            service_type=category,
            amount=final_amount,
            currency="XAF",
            provider=gateway,
            signature=signature,
            status=PaymentStatus.PENDING,
            idempotency_key=reference,
            metadata_json={
                "ussd": ussd_code,
                "expires_at": (
                    datetime.utcnow() + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
                ).isoformat(),
                "extra": metadata,
            },
        )

        db.add(payment)
        await db.commit()

        return PaymentResponse(
            success=True,
            status="PENDING",
            transaction_id=reference,
            ussd_code=ussd_code,
            message="Dial USSD code to confirm payment",
        )


# ======================================================
# ALIASES (for existing routers/tests)
# ======================================================

get_remaining_free_count = PaymentService.get_remaining_free_uses
record_payment = PaymentService.process_payment
