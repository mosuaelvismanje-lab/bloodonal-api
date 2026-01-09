import asyncio
import inspect
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    FreeUsageResponse,
    PaymentStatus,
)
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

# -------------------------------------------------
# ROUTER CONFIG
# -------------------------------------------------
# Tests expect:
#   GET  /v1/payments/doctor-consults/remaining
#   POST /v1/payments/doctor-consults
router = APIRouter(
    prefix="/v1/payments/doctor-consults",
    tags=["doctor-payments"],
)

# -------------------------------------------------
# SERVICE ALIASES & FALLBACKS
# -------------------------------------------------
DOCTOR_FEE = getattr(PaymentService, "DOCTOR_FEE", 300)

get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment


async def _maybe_await(func: Any, *args, **kwargs):
    """
    Call async or sync service functions safely.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


# -------------------------------------------------
# GET REMAINING FREE DOCTOR CONSULTS
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_doctor_consults(
    user_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """
    Returns remaining free doctor consultations for a user.
    """
    try:
        remaining = await _maybe_await(
            get_remaining_free_uses,
            db,
            user_id,
            category="doctor",
        )
        return FreeUsageResponse(remaining=remaining)

    except Exception as exc:
        logger.exception(
            "Error computing remaining doctor consults for user=%s", user_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining free consults",
        ) from exc


# -------------------------------------------------
# PAY FOR DOCTOR CONSULT
# -------------------------------------------------
@router.post("", response_model=PaymentResponse)
async def pay_doctor_consult(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_async_session),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Initiates a doctor consultation payment.

    Uses PaymentService to:
    - apply free-usage rules
    - create a payment record
    - initiate gateway charge

    Tests monkeypatch process_payment(), so implementation details
    must remain thin and predictable.
    """
    try:
        payment_result = await _maybe_await(
            process_payment,
            db=db,
            user_id=req.user_id,
            category="doctor",
            req=req,
            idempotency_key=x_idempotency_key,
        )

        # Service-safe fields
        reference = getattr(
            payment_result, "reference", uuid.uuid4().hex.upper()
        )
        expires_at = getattr(
            payment_result,
            "expires_at",
            datetime.now(timezone.utc),
        )

        return PaymentResponse(
            success=True,
            reference=reference,
            status=PaymentStatus.PENDING,
            expires_at=expires_at,
            message=getattr(payment_result, "message", None),
            ussd_string=getattr(payment_result, "ussd_string", None),
        )

    except Exception as exc:
        logger.exception(
            "Doctor payment failed for user=%s", getattr(req, "user_id", None)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment processing failed",
        ) from exc
