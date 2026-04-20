import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Standardized dependencies matching main.py
from app.api.dependencies import get_current_user, get_db

# ✅ MODERN REPOSITORY
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.domain.usecases import SERVICE_FREE_LIMITS_SIMPLE as SERVICE_FREE_LIMITS

# ✅ FIXED IMPORTS: Resolves the 'PaymentResponse' ImportError
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponseOut,
    FreeUsageResponse,
    PaymentStatus,
)

logger = logging.getLogger(__name__)

# -------------------------
# Router Configuration
# -------------------------
# --- FIX: Removed '/v1' from prefix to align with main.py versioning ---
router = APIRouter(
    prefix="/payments/taxi",
    tags=["taxi-payments"],
    redirect_slashes=False
)


# -------------------------------------------------
# GET REMAINING FREE TAXI RIDES
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_taxi_rides(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """
    Returns remaining free taxi rides using the standardized counter repository.
    """
    try:
        target_uid = user_id or current_user.uid
        repo = SQLAlchemyUsageRepository(db)
        used = await repo.count_uses(target_uid, "taxi")

        free_limit = SERVICE_FREE_LIMITS.get("taxi", 0)
        remaining_count = max(0, free_limit - used)

        return FreeUsageResponse(
            remaining=remaining_count,
            fee=1000 if remaining_count == 0 else 0  # 2026 Taxi Base Fee
        )

    except Exception as e:
        logger.error(f"Failed to fetch remaining taxi rides for {target_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining taxi rides",
        )


# -------------------------------------------------
# PAY FOR TAXI RIDE
# -------------------------------------------------
@router.post("", response_model=PaymentResponseOut)
async def pay_for_taxi(
        req: PaymentRequest,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiates a taxi ride usage. Consumes free ride if available, else generates USSD.
    """
    try:
        repo = SQLAlchemyUsageRepository(db)
        used = await repo.count_uses(current_user.uid, "taxi")
        free_limit = SERVICE_FREE_LIMITS.get("taxi", 0)

        # ✅ LOGIC 1: Handle Free Tier Consumption
        if used < free_limit:
            usage_ref = f"TAXI-FREE-{uuid.uuid4().hex[:8].upper()}"
            await repo.record_usage(
                user_id=current_user.uid,
                service="taxi",
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
                message="Free taxi ride recorded successfully.",
                ussd_string=None,
            )

        # ✅ LOGIC 2: Handle Paid Tier (2026 Merchant Rail)
        payment_ref = f"TAXI-PAID-{uuid.uuid4().hex[:8].upper()}"

        # 2026 Merchant USSD format: *126*2*RECIPIENT*AMOUNT#
        merchant_ussd = "*126*2*670000000*1000#"

        return PaymentResponseOut(
            success=True,
            reference=payment_ref,
            status=PaymentStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            message="Taxi payment initiated. Please check your phone for the USSD prompt.",
            ussd_string=merchant_ussd,
        )

    except Exception:
        logger.exception("Taxi payment failed for user=%s", current_user.uid)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Taxi payment processing failed",
        )