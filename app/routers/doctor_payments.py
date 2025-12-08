# app/routers/doctor_payment.py

import asyncio
import inspect
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.payment import PaymentRequest, PaymentResponse, FreeUsageResponse
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

# -----------------------------
# MATCH TEST EXPECTED ENDPOINTS
# -----------------------------
# Tests call:
#   GET  /v1/payments/doctor-consults/remaining
#   POST /v1/payments/doctor-consults
router = APIRouter(
    prefix="/v1/payments/doctor-consults",
    tags=["doctor-payments"]
)

# Use fallback fee if PaymentService does not define one
DOCTOR_FEE = getattr(PaymentService, "DOCTOR_FEE", 300)

# Aliases
get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment


async def _maybe_await(func: Any, *args, **kwargs):
    """Safely call async or sync service functions."""
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


# ----------------------------------------------------
# GET REMAINING FREE DOCTOR CONSULTS
# GET /v1/payments/doctor-consults/remaining
# ----------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_doctor_consults(
    user_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        remaining = await _maybe_await(
            get_remaining_free_uses,
            db,
            user_id,
            category="doctor"
        )
        return FreeUsageResponse(remaining=remaining)
    except Exception as exc:
        logger.exception("Error computing remaining doctor consults for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free consults"
        ) from exc


# ----------------------------------------------------
# PAY FOR DOCTOR CONSULT
# POST /v1/payments/doctor-consults
# ----------------------------------------------------
@router.post("", response_model=PaymentResponse)
async def pay_doctor_consult(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_async_session),
    x_idempotency_key: str = Header(default=None),
):
    try:
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            category="doctor",
            req=req
        )

        # fallback if service does not set the amount
        amount = getattr(payment_result, "amount", DOCTOR_FEE)

        return PaymentResponse(
            success=True,
            transaction_id=payment_result.transaction_id,
            amount=amount
        )

    except Exception as exc:
        logger.exception("Doctor payment failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        ) from exc
