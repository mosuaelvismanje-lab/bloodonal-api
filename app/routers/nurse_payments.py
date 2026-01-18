import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligned Dependencies: Using the same pattern as Bike/Doctor
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
    prefix="/payments/nurse-services",
    tags=["nurse-payments"],
    redirect_slashes=False
)


# -------------------------------------------------
# GET REMAINING FREE NURSE USES
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_nurse_uses(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),
):
    """
    Returns remaining free nurse services for a user following the Bike pattern.
    """
    try:
        # Priority: Query Parameter > Authenticated User UID
        target_uid = user_id or getattr(current_user, "uid", "")

        remaining = await PaymentService.get_remaining_free_uses(
            db,
            target_uid,
            category="nurse",
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception:
        logger.exception("Error computing remaining nurse uses")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free nurse services",
        )


# -------------------------------------------------
# PAY FOR NURSE SERVICE
# -------------------------------------------------
@router.post("", response_model=PaymentResponse)
async def pay_nurse_service(
        req: PaymentRequest,  # ✅ Standardized: No longer using NursePaymentRequest
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiates a nurse service payment using current_user.uid.
    Matches the standardized PaymentRequest pattern.
    """
    try:
        # Step 1: Secure Identity from Token
        user_id = current_user.uid

        # Step 2: Process via common PaymentService
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=user_id,
            category="nurse",
            req=req,
            idempotency_key=x_idempotency_key,
        )

        # Step 3: Standardized Response Mapping (Safely handling attributes)
        return PaymentResponse(
            success=True,
            reference=getattr(payment_result, "reference", uuid.uuid4().hex.upper()),
            status=PaymentStatus.PENDING,
            expires_at=getattr(payment_result, "expires_at", datetime.now(timezone.utc)),
            message=getattr(payment_result, "message", "Nurse service payment initiated"),
            ussd_string=getattr(payment_result, "ussd_string", None),
        )

    except Exception:
        logger.exception("Nurse payment failed for user=%s", getattr(current_user, "uid", None))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed",
        )


