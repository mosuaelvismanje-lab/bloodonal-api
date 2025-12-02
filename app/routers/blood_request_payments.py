# app/routers/blood_request_payment.py
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

router = APIRouter(prefix="/v1/blood-requests", tags=["blood-request-payments"])

# Try to import BLOOD_REQUEST_FEE from the service layer; fallback to default
try:
    from app.services.payment_service import BLOOD_REQUEST_FEE
except ImportError:
    BLOOD_REQUEST_FEE = 300  # fallback fee


async def _maybe_await(func: Any, *args, **kwargs):
    """
    If the service function is async → await it.
    If it's sync → offload to a background thread.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get("/remaining", response_model=FreeConsultsResponse)
async def remaining_free_blood_requests(
    user_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Return how many free blood-request operations remain for a user.
    """
    try:
        remaining = await _maybe_await(
            get_remaining_free_count,
            db,
            user_id,
            payment_type="blood_request"
        )

        return FreeConsultsResponse(remaining=remaining)

    except Exception as exc:
        logger.exception("Error computing remaining blood requests for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining blood requests"
        ) from exc


@router.post("/", response_model=PaymentResponse)
async def pay_for_blood_request(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Charge for a blood request, or mark it free if user still has free quota.
    """
    try:
        remaining = await _maybe_await(
            get_remaining_free_count,
            db,
            req.user_id,
            payment_type="blood_request"
        )

        amount = 0 if remaining > 0 else BLOOD_REQUEST_FEE

        tx_id = await _maybe_await(
            record_payment,
            db,
            req.user_id,
            payment_type="blood_request",
            amount=amount
        )

        return PaymentResponse(success=True, transaction_id=tx_id)

    except ValueError as ve:
        logger.warning("Validation error for user=%s: %s", req.user_id, ve)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )

    except Exception as exc:
        logger.exception("Payment processing for blood request failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        ) from exc
