import asyncio
import uuid
import hashlib
from datetime import datetime, timedelta, timezone
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
    return uuid.uuid4().hex.upper()


def generate_signature(reference: str, amount: float, phone: str) -> str:
    raw = f"{reference}:{amount}:{phone}"
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_ussd(gateway: str, amount: float) -> str:
    gateway = gateway.upper()
    config = PAYMENT_GATEWAYS.get(gateway, PAYMENT_GATEWAYS["MTN"])
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
    • Schema-compliant responses for Bike/Doctor/Nurse
    """

    @staticmethod
    async def get_remaining_free_uses(
        db: AsyncSession,
        user_id: str,
        category: str,
    ) -> int:
        used = await get_free_usage_count(db, user_id, category)
        limit = FREE_LIMITS.get(category, 0)
        return max(limit - used, 0)

    @staticmethod
    async def process_payment(
        db: AsyncSession,
        *,
        user_id: str,
        user_phone: str,
        category: str,
        gateway: Optional[str] = "MTN",
        req_data: Union[Dict, object],
    ) -> PaymentResponse:
        """
        Processes payment and returns a response compliant with PaymentResponse schema.
        """

        # Extract metadata
        metadata = (
            getattr(req_data, "metadata", None)
            if not isinstance(req_data, dict)
            else req_data.get("metadata")
        )

        # Step 1: free usage check
        free_left = await PaymentService.get_remaining_free_uses(
            db, user_id, category
        )

        # Step 2: determine expiration
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)

        # Step 3: check if service is blood request (always free)
        is_blood = (category == "blood_request")
        final_amount = 0 if (free_left > 0 or is_blood) else BASE_FEE.get(category, 0)

        # -------------------------
        # FREE FLOW
        # -------------------------
        if final_amount == 0:
            await increment_usage_count(db, user_id, category)
            ref = f"FREE-{uuid.uuid4().hex[:8].upper()}"

            return PaymentResponse(
                success=True,
                status=PaymentStatus.COMPLETED,
                message="Free usage applied successfully",
                transaction_id=ref,
                reference=ref,  # Added for new schema compliance
                ussd_code=None,
                expires_at=expires_at  # Added for new schema compliance
            )

        # -------------------------
        # PAID FLOW (USSD)
        # -------------------------
        active_gateway = (gateway or "MTN").upper()
        reference = generate_reference()
        signature = generate_signature(reference, final_amount, user_phone)
        ussd_code = generate_ussd(active_gateway, final_amount)

        payment = Payment(
            reference=reference,
            user_id=user_id,
            user_phone=user_phone,
            service_type=category,
            amount=final_amount,
            currency="XAF",
            provider=active_gateway,
            signature=signature,
            status=PaymentStatus.PENDING,
            idempotency_key=reference,
            metadata_json={
                "ussd": ussd_code,
                "expires_at": expires_at.isoformat(),
                "extra": metadata,
            },
        )

        db.add(payment)
        await db.commit()

        return PaymentResponse(
            success=True,
            status=PaymentStatus.PENDING,
            transaction_id=reference,
            reference=reference, # Explicitly mapped for BikePaymentResponse
            ussd_code=ussd_code,
            expires_at=expires_at,
            message="Please dial the USSD code on your phone to complete payment"
        )


# ======================================================
# ALIASES
# ======================================================

get_remaining_free_count = PaymentService.get_remaining_free_uses
record_payment = PaymentService.process_payment