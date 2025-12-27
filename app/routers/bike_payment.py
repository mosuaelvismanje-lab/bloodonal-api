# app/routers/bike_payment.py

import asyncio
import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.payment import PaymentRequest, PaymentResponse, FreeUsageResponse
from app.services.payment_service import PaymentService
from app.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/bike-payments", tags=["bike-payments"])

# Use fallback fee if not defined in PaymentService
BIKE_FEE = getattr(PaymentService, "BIKE_FEE", 300)

# Convenience aliases
get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment


async def _maybe_await(func: Any, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


# -------------------------
# GET REMAINING FREE BIKE RIDES
# -------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_bike_rides(
    user_id: str, db: AsyncSession = Depends(get_async_session)
):
    try:
        remaining = await _maybe_await(
            get_remaining_free_uses,
            db,
            user_id,
            category="biker"
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception as exc:
        logger.exception("Error fetching remaining bike rides for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining bike rides"
        ) from exc


# -------------------------
# PAY FOR BIKE RIDE
# -------------------------
@router.post("/", response_model=PaymentResponse)
async def pay_for_bike(req: PaymentRequest, db: AsyncSession = Depends(get_async_session)):
    try:
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            category="biker",
            req=req
        )

        return PaymentResponse(
            success=True,
            transaction_id=payment_result.transaction_id,
            amount=payment_result.amount  # <-- fixed to match PaymentResponse schema
        )

    except Exception as exc:
        logger.exception("Bike payment failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bike payment failed"
        ) from exc
