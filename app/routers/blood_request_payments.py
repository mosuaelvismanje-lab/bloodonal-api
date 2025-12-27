# app/routers/blood_request_payment.py

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

router = APIRouter(prefix="/v1/blood-requests", tags=["blood-request-payments"])

# Use fallback fee if not defined in PaymentService
BLOOD_REQUEST_FEE = getattr(PaymentService, "BLOOD_REQUEST_FEE", 300)

# Convenience aliases for router usage
get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment


async def _maybe_await(func: Any, *args, **kwargs):
    """
    Await async functions or run sync functions in a thread.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


# -------------------------
# GET REMAINING FREE BLOOD REQUESTS
# -------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_blood_requests(
    user_id: str, db: AsyncSession = Depends(get_async_session)
):
    try:
        remaining = await _maybe_await(
            get_remaining_free_uses,
            db,
            user_id,
            category="blood_request"
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception as exc:
        logger.exception("Error computing remaining blood requests for user=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining blood requests"
        ) from exc


# -------------------------
# PAY FOR BLOOD REQUEST
# -------------------------
@router.post("/", response_model=PaymentResponse)
async def pay_for_blood_request(
    req: PaymentRequest, db: AsyncSession = Depends(get_async_session)
):
    try:
        # Process the payment (free or paid)
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            category="blood_request",
            req=req
        )

        # Return unified PaymentResponse
        return PaymentResponse(
            success=True,
            transaction_id=payment_result.transaction_id,
            amount=payment_result.amount  # use the field from PaymentResponse
        )

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
