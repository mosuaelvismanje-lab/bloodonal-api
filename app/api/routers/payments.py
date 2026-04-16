import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Registry & Orchestrator (Centralized Logic)
from app.services.registry import registry
from app.services.orchestrator import service_orchestrator

# ✅ Repository & Models (Data Access Layer)
from app.api.dependencies import get_current_user, get_db_session
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.repositories.payment_repo import PaymentRepository
from app.models.payment import PaymentStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/payments", tags=["Payment Stack"])


# --- Schemas (Standardized for Android/Moshi) ---

class RemainingWithFeeResponse(BaseModel):
    remaining: int
    fee: int
    promo_message: Optional[str] = None


class PaymentRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\d{9,13}$")


class PaymentResponseOut(BaseModel):
    success: bool = True
    reference: str  # Now returning UUID strings
    status: PaymentStatus
    message: Optional[str] = None
    expires_at: Optional[datetime] = None
    ussd_string: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    reference: str
    transaction_id: str


# --- Helpers ---

def get_cameroon_ussd(phone: str, amount: int) -> str:
    """Detects carrier and generates USSD push/fallback string."""
    is_mtn = phone.startswith(("67", "650", "651", "652", "653", "654", "68"))
    if is_mtn:
        return f"*126*1*{amount}#"
    return f"*150*1*1*{amount}#"


# --- Routes ---

@router.get("/{service}/remaining", response_model=RemainingWithFeeResponse)
async def get_usage_status(
        service: str,
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    meta = registry.get_service_meta(service)
    usage_repo = SQLAlchemyUsageRepository(db)

    # user.uid is a UUID object; repo handles the count
    used = await usage_repo.count_uses(user.uid, service)
    remaining = max(0, meta["free_limit"] - used)
    fee = meta["base_fee"] if meta["is_payment_globally_enabled"] else 0

    return RemainingWithFeeResponse(
        remaining=remaining,
        fee=fee,
        promo_message=meta["promo_message"]
    )


@router.post("/{service}", response_model=PaymentResponseOut)
async def initiate_payment(
        service: str,
        req: PaymentRequest,
        idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    usage_repo = SQLAlchemyUsageRepository(db)
    payment_repo = PaymentRepository(db)

    used = await usage_repo.count_uses(user.uid, service)
    fee = registry.calculate_effective_fee(service, used)

    # 1. FREE TIER: Automated Activation via Orchestrator
    if fee <= 0:
        listing = await service_orchestrator.activate_listing(
            db=db, user_id=user.uid, service_type=service, activation_ref=idempotency_key
        )
        await db.commit()
        return PaymentResponseOut(reference=str(listing.id), status=PaymentStatus.SUCCESS)

    # 2. IDEMPOTENCY: Check existing payments via Repository
    existing = await payment_repo.get_by_idempotency(idempotency_key)
    if existing:
        return PaymentResponseOut(
            reference=str(existing.id),
            status=existing.status,
            ussd_string=get_cameroon_ussd(req.phone, int(existing.amount))
        )

    # 3. PAID FLOW: Create PENDING record
    payment = await payment_repo.create_payment(
        user_id=user.uid,
        payment_type=service,
        amount=fee,
        idempotency_key=idempotency_key,
        details={"phone": req.phone}
    )

    await db.commit()

    return PaymentResponseOut(
        reference=str(payment.id),
        status=PaymentStatus.PENDING,
        ussd_string=get_cameroon_ussd(req.phone, int(fee)),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
    )


@router.post("/confirm", response_model=PaymentResponseOut)
async def confirm_payment(
        req: PaymentConfirmRequest,
        user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    payment_repo = PaymentRepository(db)

    # Update status with State Machine Guard built into Repo
    updated = await payment_repo.update_status(
        payment_id=uuid.UUID(req.reference),
        new_status=PaymentStatus.AWAITING_VERIFICATION,
        provider_tx_id=req.transaction_id
    )

    if not updated:
        raise HTTPException(status_code=400, detail="Invalid reference or already finalized")

    await db.commit()
    return PaymentResponseOut(
        reference=str(updated.id),
        status=updated.status,
        message="Verification in progress."
    )