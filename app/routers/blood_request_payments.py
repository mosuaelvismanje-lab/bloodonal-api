import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.schemas.payment import PaymentRequest, PaymentResponseOut, FreeUsageResponse
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blood-request-payments",
    tags=["blood-request-payments"],
)

# -------------------------------------------------
# PAY BLOOD REQUEST
# -------------------------------------------------
@router.post("", response_model=PaymentResponseOut)
async def pay_blood_request(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    return await PaymentService.process_payment(
        db=db,
        user_id=current_user.uid,
        user_phone=req.phone,
        category="blood-request",
    )


# -------------------------------------------------
# GET REMAINING FREE USAGE
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def get_remaining_blood_requests(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    remaining = await PaymentService.get_remaining_free_uses(
        user_id=current_user.uid,
        category="blood-request",
    )

    return FreeUsageResponse(remaining=remaining)