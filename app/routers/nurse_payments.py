# app/routers/nurse_payments.py
import asyncio
import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.nurse_payment import NursePaymentRequest, NursePaymentResponse
from app.services.payment_service import (
    get_remaining_free_count,
    record_payment
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/nurse-payments", tags=["nurse-payments"])

# If your payment_service defines a nurse fee, import it safely:
try:
    from app.services.payment_service import NURSE_FEE
except ImportError:
    NURSE_FEE = 300  # fallback value


async def _maybe_await(func: Any, *args, **kwargs):
    """
    If func is async → await it.
    If func is sync → run it in a background thread.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/remaining", response_model=dict)
async def remaining_nurse_consults(
    user_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Return remaining free nurse consultations for a specific user.
    """
    try:
        remaining = await _maybe_await(
            get_remaining_free_count, db, user_id, payment_type="nurse"
        )
        return {"remaining": remaining}

    except Exception as exc:
        logger.exception("Error computing remaining nurse consults for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining nurse consults"
        ) from exc


@router.post("/", response_model=NursePaymentResponse)
async def pay_for_nurse(
    req: NursePaymentRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Charge for a nurse service, or mark it as free if the user has free quota.
    """
    try:
        remaining_free = await _maybe_await(
            get_remaining_free_count, db, req.user_id, payment_type="nurse"
        )

        amount = 0 if remaining_free > 0 else NURSE_FEE

        tx_id = await _maybe_await(
            record_payment,
            db,
            req.user_id,
            payment_type="nurse",
            amount=amount
        )

        return NursePaymentResponse(success=True, transaction_id=tx_id)

    except ValueError as ve:
        # service layer signaled a validation issue
        logger.warning("Payment validation failed for user=%s: %s", req.user_id, ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )

    except Exception as exc:
        logger.exception("Payment processing failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        ) from exc
