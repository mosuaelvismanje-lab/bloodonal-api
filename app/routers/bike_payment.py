import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Project Dependencies - Updated to match main.py naming
from app.api.dependencies import get_current_user, get_db
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse, BikeFreeUsageResponse
from app.schemas.payment import PaymentStatus

# ✅ MODERN REPOSITORY
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.domain.usecases import SERVICE_FREE_LIMITS_SIMPLE as SERVICE_FREE_LIMITS

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/payments/bike",
    tags=["BikePayments"],
    redirect_slashes=False
)


# -------------------------
# GET REMAINING FREE BIKE RIDES
# -------------------------
@router.get("/remaining", response_model=BikeFreeUsageResponse)
async def remaining_free_bike_rides(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """
    Check remaining free bike rides for the authenticated user.
    Uses the 2026 UsageCounter logic.
    """
    try:
        usage_repo = SQLAlchemyUsageRepository(db)
        used = await usage_repo.count_uses(current_user.uid, "bike")

        # Pulling limits from central domain logic (Default 2 for bikes)
        free_limit = SERVICE_FREE_LIMITS.get("bike", 2)
        remaining_count = max(0, free_limit - used)

        return BikeFreeUsageResponse(
            remaining=remaining_count,
            fee=500 if remaining_count == 0 else 0  # Standard 2026 bike fee
        )
    except Exception as e:
        logger.error(f"Error fetching bike rides for {current_user.uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining bike rides",
        )


# -------------------------
# PAY FOR BIKE RIDE
# -------------------------
@router.post("", response_model=BikePaymentResponse)
async def pay_for_bike(
        req: BikePaymentRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiate bike payment or consume free ride.
    Integrated with 2026 SMS-Bypass USSD generation.
    """
    try:
        usage_repo = SQLAlchemyUsageRepository(db)
        used = await usage_repo.count_uses(current_user.uid, "bike")
        free_limit = SERVICE_FREE_LIMITS.get("bike", 2)

        # 1. Handle Free Ride logic
        if used < free_limit:
            # Generate a unique tracking ID for this specific usage
            internal_ref = f"BIKE-FREE-{uuid.uuid4().hex[:8].upper()}"

            await usage_repo.record_usage(
                user_id=current_user.uid,
                service="bike",
                paid=False,
                amount=0.0,
                request_id=internal_ref
            )
            await db.commit()

            return BikePaymentResponse(
                success=True,
                reference=internal_ref,
                status=PaymentStatus.SUCCESS,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                message="Free bike ride recorded successfully.",
                ussd_string=None
            )

        # 2. Handle Paid Ride logic (2026 Merchant USSD Rail)
        # In a full implementation, this would call your PaymentService
        transaction_id = f"BIKE-PAID-{uuid.uuid4().hex[:8].upper()}"

        # ✅ 2026 Merchant USSD Format: *126*2*RECIPIENT*AMOUNT#
        # Using a simulated merchant number for the bike service
        merchant_ussd = f"*126*2*676657577*500#"

        return BikePaymentResponse(
            success=True,
            reference=transaction_id,
            status=PaymentStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            message=f"Quota exceeded. Please dial the USSD prompt on {req.phone}.",
            ussd_string=merchant_ussd
        )

    except Exception:
        logger.exception("Bike payment failed for user=%s", current_user.uid)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bike payment failed",
        )