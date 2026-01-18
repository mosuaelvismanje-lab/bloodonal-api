import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Consistent Dependencies (Bike/Doctor Pattern)
from app.api.dependencies import get_current_user, get_db_session
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    FreeUsageResponse,
    PaymentStatus,
)
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

# -------------------------
# Router Configuration
# -------------------------
router = APIRouter(
    # FIX: Removed "/v1" because main.py handles versioning via api_router
    prefix="/payments/taxi",
    tags=["taxi-payments"],
    redirect_slashes=False  # ✅ Standardized for stable testing
)

# -------------------------------------------------
# GET REMAINING FREE TAXI RIDES
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_taxi_rides(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user), # ✅ Added for pattern consistency
):
    """
    Returns remaining free taxi rides for a user.
    """
    try:
        # Step 1: Secure target user ID (Query param > Auth Token)
        target_uid = user_id or getattr(current_user, "uid", "")

        # Step 2: Use PaymentService for unified logic
        remaining = await PaymentService.get_remaining_free_uses(
            db,
            target_uid,
            category="taxi",
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception:
        logger.exception("Failed to fetch remaining taxi rides")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining taxi rides",
        )


# -------------------------------------------------
# PAY FOR TAXI RIDE
# -------------------------------------------------
@router.post("", response_model=PaymentResponse) # ✅ Removed trailing slash
async def pay_for_taxi(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user), # ✅ Matches standard
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiates a taxi ride payment using current_user.uid.
    Uses PaymentService to ensure idempotency and schema consistency.
    """
    try:
        # Step 1: Process via unified service
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=current_user.uid,
            category="taxi",
            req=req,
            idempotency_key=x_idempotency_key,
        )

        # Step 2: Standardized Response Mapping
        # Safely extracts attributes returned by the PaymentService
        return PaymentResponse(
            success=True,
            reference=getattr(payment_result, "reference", uuid.uuid4().hex.upper()),
            status=PaymentStatus.PENDING,
            expires_at=getattr(payment_result, "expires_at", datetime.now(timezone.utc)),
            message=getattr(payment_result, "message", "Taxi ride payment initiated"),
            ussd_string=getattr(payment_result, "ussd_string", None),
        )

    except Exception:
        logger.exception(
            "Taxi payment failed for user=%s",
            getattr(current_user, "uid", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Taxi payment failed",
        )

