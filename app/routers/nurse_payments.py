# app/routers/nurse_payments.py
import asyncio
import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.nurse_payment import NursePaymentRequest, NursePaymentResponse
from app.services.payment_service import get_remaining_free_count, record_payment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/nurse-payments", tags=["nurse-payments"])

# fallback nurse fee if your service layer doesn't expose one
DEFAULT_NURSE_FEE = 300


async def _maybe_await(func: Any, *args, **kwargs):
    """
    If `func` is async, await it; otherwise run it in a thread to avoid blocking.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/remaining", response_model=dict)
async def remaining_nurse_consults(user_id: str, db: AsyncSession = Depends(get_async_session)):
    """
    Return remaining free nurse consultations for a user.
    """
    try:
        remaining = await _maybe_await(get_remaining_free_count, db, user_id, payment_type="nurse_consult")
        return {"remaining": remaining}
    except Exception as exc:
        logger.exception("Error computing remaining nurse consults for user=%s", user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to compute remaining consults") from exc


@router.post("/", response_model=NursePaymentResponse)
async def pay_for_nurse(req: NursePaymentRequest, db: AsyncSession = Depends(get_async_session)):
    """
    Charge for a nurse consult (or mark as free if user has quota).
    """
    try:
        free_left = await _maybe_await(get_remaining_free_count, db, req.user_id, payment_type="nurse_consult")
        amount_to_pay = 0 if free_left > 0 else getattr(__import__("app.services.payment_service", fromlist=[""]), "NURSE_FEE", DEFAULT_NURSE_FEE)

        tx_id = await _maybe_await(record_payment, db, req.user_id, payment_type="nurse_consult", amount=amount_to_pay)
        return NursePaymentResponse(success=True, transaction_id=tx_id)

    except ValueError as ve:
        logger.warning("Payment validation error for user=%s: %s", req.user_id, ve)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))

    except Exception as exc:
        logger.exception("Payment processing failed for user=%s", req.user_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Payment processing failed") from exc
