# app/routers/nurse_payments.py

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

router = APIRouter(prefix="/v1/nurse-payments", tags=["nurse-payments"])

# Optional fallback fee if not defined
NURSE_FEE = getattr(PaymentService, "NURSE_FEE", 200)

# Convenience aliases
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
# GET REMAINING FREE NURSE CONSULTS
# -------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_nurse_consults(user_id: str, db: AsyncSession = Depends(get_async_session)):
    try:
        remaining = await _maybe_await(
            get_remaining_free_uses,
            db,
            user_id,
            category="nurse"
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception as exc:
        logger.exception("Error computing remaining nurse consults for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining nurse consults"
        ) from exc


# -------------------------
# PAY FOR NURSE CONSULT
# -------------------------
@router.post("/", response_model=PaymentResponse)
async def pay_for_nurse(req: PaymentRequest, db: AsyncSession = Depends(get_async_session)):
    try:
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            category="nurse",
            req=req
        )

        # Use 'amount' from PaymentResponse (fallback to NURSE_FEE if missing)
        amount = getattr(payment_result, "amount", NURSE_FEE)

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
        logger.exception("Payment processing failed for user=%s", req.user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed"
        ) from exc

