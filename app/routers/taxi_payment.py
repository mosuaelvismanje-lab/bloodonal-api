# app/routers/taxi_payment.py

import asyncio
import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.payment import PaymentRequest, PaymentResponse, FreeUsageResponse
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/taxi-payments", tags=["taxi-payments"])

# Optional fallback fee
TAXI_FEE = getattr(PaymentService, "TAXI_FEE", 150)

# Aliases for convenience
get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment


async def _maybe_await(func: Any, *args, **kwargs):
    """
    Safely call async or sync service functions.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


# -------------------------
# GET REMAINING FREE TAXI RIDES
# -------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_taxi_rides(user_id: str, db: AsyncSession = Depends(get_async_session)):
    try:
        remaining = await _maybe_await(
            get_remaining_free_uses,
            db,
            user_id,
            category="taxi"
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception as exc:
        logger.exception("Failed to fetch remaining taxi rides for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining taxi rides"
        ) from exc


# -------------------------
# PAY FOR TAXI RIDE
# -------------------------
@router.post("/", response_model=PaymentResponse)
async def pay_for_taxi(req: PaymentRequest, db: AsyncSession = Depends(get_async_session)):
    try:
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            category="taxi",
            req=req
        )

        # Use 'amount' from PaymentResponse (fallback to TAXI_FEE if missing)
        amount = getattr(payment_result, "amount", TAXI_FEE)

        return PaymentResponse(
            success=True,
            transaction_id=payment_result.transaction_id,
            amount=amount
        )

    except ValueError as ve:
        logger.warning("Payment validation failed for user=%s: %s", req.user_id, ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )

    except Exception as exc:
        logger.exception("Taxi payment failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Taxi payment failed"
        ) from exc

