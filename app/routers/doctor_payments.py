# app/routers/doctor_payment.py
import asyncio
import inspect
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.database import get_async_session
from app.schemas import PaymentRequest, PaymentResponse, FreeConsultsResponse
from app.services.payment_service import get_remaining_free_count, record_payment, FEE_AMOUNT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/payments", tags=["doctor-payments"])


async def _maybe_await(func: Any, *args, **kwargs):
    """
    If func is async, await it. If it's sync, run it in a background thread
    to avoid blocking the event loop. Returns whatever the underlying function returns.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/doctor-consults/remaining", response_model=FreeConsultsResponse)
async def remaining_doctor_consults(user_id: str, db: AsyncSession = Depends(get_async_session)):
    """
    Return how many free doctor consultations remain for the given user_id.
    Delegates to the service layer; works with both sync and async implementations.
    """
    try:
        remaining = await _maybe_await(get_remaining_free_count, db, user_id, payment_type="doctor")
        return FreeConsultsResponse(remaining=remaining)
    except Exception as exc:
        logger.exception("Error computing remaining doctor consults for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free consults"
        ) from exc


@router.post("/doctor-consults", response_model=PaymentResponse)
async def pay_doctor_consult(req: PaymentRequest, db: AsyncSession = Depends(get_async_session)):
    """
    Charge (or mark as free) a doctor consultation for the user in req.user_id.

    - If user still has free quota, amount charged is 0.
    - record_payment must return a transaction id (string).
    - This endpoint supports both sync and async service implementations.
    """
    try:
        used = await _maybe_await(get_remaining_free_count, db, req.user_id, payment_type="doctor")
        amount = 0 if used > 0 else FEE_AMOUNT

        # record_payment may be sync or async. We run it via _maybe_await.
        tx_id = await _maybe_await(record_payment, db, req.user_id, payment_type="doctor", amount=amount)

        return PaymentResponse(success=True, transaction_id=tx_id)

    except ValueError as ve:
        # Service layer raised a validation-like error (e.g., invalid user)
        logger.warning("Payment validation failed for user=%s: %s", req.user_id, ve)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    except Exception as exc:
        logger.exception("Payment processing failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        ) from exc
