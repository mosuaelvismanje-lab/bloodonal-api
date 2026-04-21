import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponseOut,
    FreeUsageResponse,
)
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

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
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns remaining free nurse services via the unified PaymentService.
    """
    try:
        target_uid = user_id or current_user.uid

        remaining = await PaymentService.get_remaining_free_uses(
            db=db,
            user_id=target_uid,
            category="nurse-services",
        )

        return FreeUsageResponse(
            remaining=remaining,
            fee=1500 if remaining == 0 else 0
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
    Initiates nurse service usage via the unified PaymentService.
    """
    try:
        payment_out = await PaymentService.process_payment(
            db=db,
            user_id=current_user.uid,
            user_phone=req.phone,
            category="nurse-services",
            req_data=req.model_dump() if hasattr(req, "model_dump") else req.dict(),
        )

        return payment_out

    except Exception as exc:
        logger.exception("Nurse payment failed for user=%s", current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(exc)}",
        )