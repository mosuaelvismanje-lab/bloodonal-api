import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligned Dependencies: Using get_db to match main.py lifespan
from app.api.dependencies import get_current_user, get_db

# ✅ MODERN REPOSITORY
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.domain.usecases import SERVICE_FREE_LIMITS_SIMPLE as SERVICE_FREE_LIMITS

# ✅ FIXED IMPORTS: Standardized to PaymentResponseOut to solve ImportError
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponseOut,  # Changed from PaymentResponse
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
    prefix="/v1/payments/doctor-consults",
    tags=["doctor-payments"],
    redirect_slashes=False
)


# -------------------------------------------------
# GET REMAINING FREE DOCTOR CONSULTS
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_doctor_consults(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """
    Returns remaining free doctor consultations for the authenticated user.
    """
    try:
        target_uid = user_id or current_user.uid
        usage_repo = SQLAlchemyUsageRepository(db)

        # 'doctor' service key matches domain limits
        used = await usage_repo.count_uses(target_uid, "doctor")
        free_limit = SERVICE_FREE_LIMITS.get("doctor", 0)

        remaining_count = max(0, free_limit - used)

        return FreeUsageResponse(
            remaining=remaining_count,
            fee=2000 if remaining_count == 0 else 0  # Standard 2026 Doctor Fee in XAF
        )

    except Exception as e:
        logger.error(f"Error computing remaining doctor consults for {target_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free consults",
        )


# -------------------------------------------------
# PAY FOR DOCTOR CONSULT
# -------------------------------------------------
@router.post("", response_model=PaymentResponseOut)
async def pay_doctor_consult(
        req: PaymentRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiates a doctor consultation. Records free usage or triggers payment USSD.
    """
    try:
        usage_repo = SQLAlchemyUsageRepository(db)
        used = await usage_repo.count_uses(current_user.uid, "doctor")
        free_limit = SERVICE_FREE_LIMITS.get("doctor", 0)

        # ✅ LOGIC 1: Handle Free Tier Consumption
        if used < free_limit:
            ref_id = f"DOC-FREE-{uuid.uuid4().hex[:8].upper()}"
            await usage_repo.record_usage(
                user_id=current_user.uid,
                service="doctor",
                paid=False,
                amount=0.0,
                request_id=ref_id
            )
            await db.commit()

            return PaymentResponseOut(
                success=True,
                reference=ref_id,
                status=PaymentStatus.SUCCESS,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                message="Free doctor consultation recorded successfully.",
                ussd_string=None,
            )

        # ✅ LOGIC 2: Handle Paid Tier (2026 Merchant USSD Flow)
        payment_ref = f"DOC-PAID-{uuid.uuid4().hex[:8].upper()}"

        # Standard Merchant Code for Doctor Service (Simulated)
        # Format: *126*2*RECIPIENT*AMOUNT#
        merchant_ussd = "*126*2*671234567*2000#"

        return PaymentResponseOut(
            success=True,
            reference=payment_ref,
            status=PaymentStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            message="Doctor consultation payment initiated. Please dial the USSD prompt.",
            ussd_string=merchant_ussd,
        )

    except Exception as exc:
        logger.exception("Doctor payment failed for user=%s", current_user.uid)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(exc)}",
        )