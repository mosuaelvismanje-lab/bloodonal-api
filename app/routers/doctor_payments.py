import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligning with Bike pattern dependencies
from app.api.dependencies import get_current_user, get_db_session
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    FreeUsageResponse,
    PaymentStatus,
)
from app.services.payment_service import PaymentService

# -------------------------
# Logger Configuration
# -------------------------
logger = logging.getLogger(__name__)

# -------------------------
# Router Configuration
# -------------------------
router = APIRouter(
    prefix="/payments/doctor-consults",
    tags=["doctor-payments"],
    redirect_slashes=False  # Aligned with Bike
)

# -------------------------------------------------
# GET REMAINING FREE DOCTOR CONSULTS
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_doctor_consults(
    user_id: Optional[str] = None, # Matches Bike pattern optional param
    db: AsyncSession = Depends(get_db_session), # Changed to get_db_session
):
    """
    Returns remaining free doctor consultations for a user.
    """
    try:
        # Using PaymentService directly as a static/class method
        remaining = await PaymentService.get_remaining_free_uses(
            db,
            user_id or "",
            category="doctor",
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception:
        logger.exception("Error computing remaining doctor consults")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free consults",
        )


# -------------------------------------------------
# PAY FOR DOCTOR CONSULT
# -------------------------------------------------
@router.post("", response_model=PaymentResponse)
async def pay_doctor_consult(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db_session), # Changed to get_db_session
    current_user = Depends(get_current_user),     # ✅ ADDED: Same as Bike
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiates a doctor consultation payment using current_user.uid.
    Matches the Bike pattern to avoid body-schema attribute errors.
    """
    try:
        # Step 1: Use user_id from the authenticated token, just like Bike
        user_id = current_user.uid

        # Step 2: Process payment
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=user_id,
            category="doctor",
            req=req,
            idempotency_key=x_idempotency_key,
        )

        # Step 3: Map to response
        return PaymentResponse(
            success=True,
            reference=getattr(payment_result, "reference", uuid.uuid4().hex.upper()),
            status=PaymentStatus.PENDING,
            expires_at=getattr(payment_result, "expires_at", datetime.now(timezone.utc)),
            message=getattr(payment_result, "message", "Doctor consultation payment initiated"),
            ussd_string=getattr(payment_result, "ussd_string", None),
        )

    except Exception:
        logger.exception("Doctor payment failed for user=%s", getattr(current_user, "uid", None))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed",
        )