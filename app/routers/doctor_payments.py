# app/routers/doctor_payment.py
import asyncio
import inspect
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.database import get_async_session
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    FreeConsultsResponse
)
from app.services.payment_service import (
    get_remaining_free_count,
    process_payment
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/payments/doctor",
    tags=["doctor-payments"]
)


async def _maybe_await(func: Any, *args, **kwargs):
    """
    Allows router to call both sync + async service functions safely.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)

    return await asyncio.to_thread(func, *args, **kwargs)


# ----------------------------------------------------------
#   CHECK REMAINING FREE DOCTOR CONSULTATIONS
# ----------------------------------------------------------

@router.get("/consult/remaining", response_model=FreeConsultsResponse)
async def remaining_doctor_consults(
    user_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Return how many free doctor consultations a user has left.
    """
    try:
        remaining = await _maybe_await(
            get_remaining_free_count,
            db,
            user_id,
            payment_type="doctor"
        )

        return FreeConsultsResponse(remaining=remaining)

    except Exception as exc:
        logger.exception(
            "Error computing doctor consults remaining",
            extra={"user_id": user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free consults"
        ) from exc


# ----------------------------------------------------------
#     PROCESS A DOCTOR CONSULTATION PAYMENT
# ----------------------------------------------------------

@router.post("/consult", response_model=PaymentResponse)
async def pay_doctor_consult(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_async_session),
    x_idempotency_key: str = Header(default=None),
):
    """
    Process a doctor consultation:
      • Free if quota remains
      • Otherwise charge billing amount
      • Idempotent (safe from duplicate payments)
    """
    try:
        logger.info(
            "Doctor consult payment request",
            extra={"user_id": req.user_id, "idempotency": x_idempotency_key}
        )

        # Let service layer compute quota, charge amount, create record, etc.
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            payment_type="doctor",
            idempotency_key=x_idempotency_key
        )

        # Router only returns response — it does NOT charge external providers.
        return PaymentResponse(
            success=True,
            transaction_id=payment_result.transaction_id,
            amount=payment_result.amount_charged
        )

    except ValueError as exc:
        # validation issue (invalid user, invalid idempotency, etc)
        raise HTTPException(status_code=400, detail=str(exc))

    except Exception as exc:
        logger.exception(
            "Doctor payment failed",
            extra={"user_id": req.user_id}
        )
        raise HTTPException(
            status_code=500,
            detail="Payment processing failed"
        ) from exc
