import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.config import settings

from app.domain.usecases import SERVICE_FREE_LIMITS_SIMPLE as SERVICE_FREE_LIMITS
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponseOut,
    FreeUsageResponse,
    PaymentStatus,
)
from app.services.payment_service import generate_reference

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payments/taxi",
    tags=["taxi-payments"],
    redirect_slashes=False,
)

# ======================================================
# GET REMAINING FREE TAXI RIDES
# ======================================================
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_taxi_rides(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns remaining free taxi rides using usage repository.
    """

    target_uid = user_id or current_user.uid

    try:
        repo = SQLAlchemyUsageRepository(db)

        # FIX: safe async usage count
        used = await repo.count_uses(target_uid, "taxi")

        free_limit = SERVICE_FREE_LIMITS.get("taxi", 0)
        remaining_count = max(0, int(free_limit) - int(used))

        return FreeUsageResponse(
            remaining=remaining_count,
            fee=settings.FEE_TAXI_REQUEST if remaining_count == 0 else 0,
        )

    except Exception as e:
        logger.error(f"Failed to fetch remaining taxi rides for {target_uid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining taxi rides",
        )


# ======================================================
# PAY FOR TAXI RIDE
# ======================================================
@router.post("", response_model=PaymentResponseOut)
async def pay_for_taxi(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Consumes free taxi ride if available,
    otherwise returns USSD payment request.
    """

    repo = SQLAlchemyUsageRepository(db)

    try:
        # FIX: correct repo contract (free_limit is correct)
        was_consumed = await repo.try_consume_free_usage(
            user_id=current_user.uid,
            service="taxi",
            free_limit=SERVICE_FREE_LIMITS.get("taxi", 0),
        )

        if was_consumed:
            await db.commit()

            return PaymentResponseOut(
                success=True,
                reference=generate_reference(),
                status=PaymentStatus.SUCCESS,
                message="Free taxi ride recorded.",
            )

        # ==================================================
        # Paid fallback flow
        # ==================================================
        fee = settings.FEE_TAXI_REQUEST
        payment_ref = generate_reference()

        return PaymentResponseOut(
            success=True,
            reference=payment_ref,
            status=PaymentStatus.PENDING,
            ussd_string=f"*126*2*{settings.ADMIN_MTN_NUMBER}*{fee}#",
            message="Dial the USSD code to complete payment.",
        )

    except Exception as e:
        await db.rollback()
        logger.exception(f"Taxi payment error: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed",
        )