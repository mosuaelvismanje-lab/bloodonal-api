from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from typing import Optional
import logging
from datetime import datetime, timedelta, timezone
import uuid
import hashlib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.domain.usecases import SERVICE_FEES, SERVICE_FREE_LIMITS
from app.data.repositories import UsageRepository
from app.models.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/payments",
    tags=["payments"],
)

PAYMENT_EXPIRY_MINUTES = 15
MY_COLLECTION_NUMBER = "670000000"  # Your MTN MoMo Merchant/Personal number


# ----------------------------
# Schemas
# ----------------------------

class RemainingWithFeeResponse(BaseModel):
    remaining: int
    fee: int


class PaymentRequest(BaseModel):
    phone: str = Field(
        ...,
        pattern=r"^\d{9}$",
        description="9-digit mobile money number"
    )


class PaymentResponseOut(BaseModel):
    reference: str
    status: PaymentStatus
    expires_at: datetime
    ussd_string: Optional[str] = None  # The hidden code for the app to dial


class PaymentConfirmRequest(BaseModel):
    reference: str
    transaction_id: str  # The ID from the MTN/Orange SMS confirmation


# ----------------------------
# Helpers
# ----------------------------

def validate_service_exists(service: str):
    if service not in SERVICE_FEES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service}' not supported"
        )


def generate_reference() -> str:
    return uuid.uuid4().hex.upper()


def generate_signature(reference: str, amount: float, phone: str) -> str:
    raw = f"{reference}:{amount}:{phone}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ----------------------------
# Routes
# ----------------------------

@router.get(
    "/{service}/remaining",
    response_model=RemainingWithFeeResponse,
    summary="Get remaining free uses and service fee",
)
async def get_remaining_with_fee(
        service: str,
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
):
    validate_service_exists(service)

    usage_repo = UsageRepository(db)
    used = await usage_repo.count(user.uid, service)

    free_limit = SERVICE_FREE_LIMITS.get(service, 0)
    remaining = max(0, free_limit - used)
    fee = SERVICE_FEES[service]

    return RemainingWithFeeResponse(
        remaining=remaining,
        fee=fee,
    )


@router.post(
    "/{service}",
    response_model=PaymentResponseOut,
    summary="Initiate a payment (manual USSD flow)",
)
async def pay_service(
        service: str,
        req: PaymentRequest,
        idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
):
    validate_service_exists(service)

    # 1️⃣ Check free usage
    usage_repo = UsageRepository(db)
    used = await usage_repo.count(user.uid, service)
    free_limit = SERVICE_FREE_LIMITS.get(service, 0)

    if used < free_limit:
        # Consume free slot
        await usage_repo.increment(user.uid, service)
        return PaymentResponseOut(
            reference="FREE-" + uuid.uuid4().hex[:10],
            status=PaymentStatus.SUCCESS,
            expires_at=datetime.now(timezone.utc),
            ussd_string=None
        )

    # 2️⃣ Prevent duplicate charge (Idempotency)
    existing = await db.scalar(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    if existing:
        ussd_code = f"*126*{MY_COLLECTION_NUMBER}*{existing.amount}#"
        return PaymentResponseOut(
            reference=existing.reference,
            status=existing.status,
            expires_at=existing.created_at + timedelta(minutes=PAYMENT_EXPIRY_MINUTES),
            ussd_string=ussd_code
        )

    # 3️⃣ Create Payment Entry
    amount = SERVICE_FEES[service]
    reference = generate_reference()
    now = datetime.now(timezone.utc)

    # Determine provider
    provider = "MTN" if req.phone.startswith(("67", "650", "651", "652", "653", "654")) else "ORANGE"

    # Generate USSD code
    ussd_code = f"*126*{MY_COLLECTION_NUMBER}*{amount}#"

    payment = Payment(
        reference=reference,
        user_id=user.uid,
        user_phone=req.phone,
        service_type=service,
        amount=amount,
        currency="XAF",
        provider=provider,
        signature=generate_signature(reference, amount, req.phone),
        status=PaymentStatus.PENDING,
        idempotency_key=idempotency_key,
        created_at=now,
    )

    db.add(payment)
    await db.commit()

    return PaymentResponseOut(
        reference=reference,
        status=PaymentStatus.PENDING,
        expires_at=now + timedelta(minutes=PAYMENT_EXPIRY_MINUTES),
        ussd_string=ussd_code
    )


@router.post(
    "/confirm",
    summary="Submit transaction ID from SMS",
)
async def confirm_payment(
        req: PaymentConfirmRequest,
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """
    User dials USSD, gets an SMS from MTN/Orange, then submits the Transaction ID here.
    """
    stmt = select(Payment).where(
        Payment.reference == req.reference,
        Payment.user_id == user.uid
    )
    payment = await db.scalar(stmt)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment reference not found"
        )

    # Assign transaction ID and set status to AWAITING_VERIFICATION
    payment.provider_tx_id = req.transaction_id
    payment.status = PaymentStatus.AWAITING_VERIFICATION

    await db.commit()

    logger.info(f"Payment verification claimed | ref={req.reference} tx_id={req.transaction_id}")

    return {"message": "Payment submitted for manual verification."}
