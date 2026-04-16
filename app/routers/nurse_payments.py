import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligned Dependencies: Using get_db to ensure session consistency
from app.api.dependencies import get_current_user, get_db

# ✅ MODERN REPOSITORY: Standardized usage tracking
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.domain.usecases import SERVICE_FREE_LIMITS_SIMPLE as SERVICE_FREE_LIMITS

# ✅ FIXED IMPORTS: Standardized to PaymentResponseOut to resolve ImportError
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponseOut,  # Renamed from PaymentResponse
    FreeUsageResponse,
    PaymentStatus,
)

# -------------------------
# Logger Configuration
# -------------------------
logger = logging.getLogger(__name__)

# -------------------------
# Router Configuration
# -------------------------
router = APIRouter(
    prefix="/v1/payments/nurse-services",
    tags=["nurse-payments"],
    redirect_slashes=False
)


# -------------------------------------------------
# GET REMAINING FREE NURSE USES
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_nurse_uses(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """
    Returns remaining free nurse services using the standardized counter repository.
    """
    try:
        target_uid = user_id or current_user.uid

        repo = SQLAlchemyUsageRepository(db)
        used = await repo.count_uses(target_uid, "nurse")

        free_limit = SERVICE_FREE_LIMITS.get("nurse", 0)
        remaining_count = max(0, free_limit - used)

        return FreeUsageResponse(
            remaining=remaining_count,
            fee=1500 if remaining_count == 0 else 0  # 2026 Nurse Service Fee in XAF
        )

    except Exception as e:
        logger.error(f"Error computing remaining nurse uses for {target_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free nurse services",
        )


# -------------------------------------------------
# PAY FOR NURSE SERVICE
# -------------------------------------------------
@router.post("", response_model=PaymentResponseOut)
async def pay_nurse_service(
        req: PaymentRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiates nurse service usage. Increments free counter or generates USSD for payment.
    """
    try:
        repo = SQLAlchemyUsageRepository(db)
        used = await repo.count_uses(current_user.uid, "nurse")
        free_limit = SERVICE_FREE_LIMITS.get("nurse", 0)

        # ✅ LOGIC 1: Handle Free Tier Consumption
        if used < free_limit:
            usage_ref = f"NURSE-FREE-{uuid.uuid4().hex[:8].upper()}"
            await repo.record_usage(
                user_id=current_user.uid,
                service="nurse",
                paid=False,
                amount=0.0,
                request_id=usage_ref
            )
            await db.commit()

            return PaymentResponseOut(
                success=True,
                reference=usage_ref,
                status=PaymentStatus.SUCCESS,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                message="Free nurse service recorded successfully.",
                ussd_string=None,
            )

        # ✅ LOGIC 2: Handle Paid Tier (2026 Merchant USSD Rail)
        payment_ref = f"NURSE-PAID-{uuid.uuid4().hex[:8].upper()}"

        # 2026 Merchant format: *126*2*RECIPIENT*AMOUNT#
        merchant_ussd = "*126*2*672223344*1500#"

        return PaymentResponseOut(
            success=True,
            reference=payment_ref,
            status=PaymentStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            message="Nurse service payment initiated. Please dial the USSD prompt.",
            ussd_string=merchant_ussd,
        )

    except Exception as exc:
        logger.exception("Nurse payment failed for user=%s", current_user.uid)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(exc)}",
        )