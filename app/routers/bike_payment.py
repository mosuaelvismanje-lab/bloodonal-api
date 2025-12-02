# app/routers/biker_payment.py
import asyncio
import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.payment import PaymentRequest, PaymentResponse, FreeConsultsResponse
from app.services.payment_service import get_remaining_free_count, record_payment
from app.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/bike-payments", tags=["bike-payments"])

try:
    from app.services.payment_service import BIKE_FEE
except ImportError:
    BIKE_FEE = 300  # fallback fee


async def _maybe_await(func: Any, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/remaining", response_model=FreeConsultsResponse)
async def remaining_free_bike_rides(user_id: str, db: AsyncSession = Depends(get_async_session)):
    try:
        remaining = await _maybe_await(
            get_remaining_free_count,
            db,
            user_id,
            payment_type="bike"
        )
        return FreeConsultsResponse(remaining=remaining)

    except Exception as exc:
        logger.exception("Error fetching remaining bike rides for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining bike rides"
        ) from exc


@router.post("/", response_model=PaymentResponse)
async def pay_for_bike(req: PaymentRequest, db: AsyncSession = Depends(get_async_session)):
    try:
        remaining = await _maybe_await(
            get_remaining_free_count,
            db,
            req.user_id,
            payment_type="bike"
        )

        amount = 0 if remaining > 0 else BIKE_FEE

        tx_id = await _maybe_await(
            record_payment,
            db,
            req.user_id,
            payment_type="bike",
            amount=amount
        )

        return PaymentResponse(success=True, transaction_id=tx_id)

    except Exception as exc:
        logger.exception("Bike payment failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bike payment failed"
        ) from exc
