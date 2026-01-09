# app/routers/taxi_payment.py
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    FreeUsageResponse,
    PaymentStatus,
)
from app.domain.usecases import ConsultationUseCase
from app.data.repositories import UsageRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/payments/taxi",
    tags=["payments"],
)


# -------------------------------------------------
# GET REMAINING FREE TAXI RIDES
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_taxi_rides(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns remaining free taxi rides.
    user_id is optional for backward compatibility.
    """
    try:
        used = await UsageRepository(db).count(user_id or "")
        free_limit = 0  # domain can override later
        return FreeUsageResponse(remaining=max(0, free_limit - used))
    except Exception:
        logger.exception("Failed to fetch remaining taxi rides")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining taxi rides",
        )


# -------------------------------------------------
# PAY FOR TAXI RIDE
# -------------------------------------------------
@router.post("/", response_model=PaymentResponse)
async def pay_for_taxi(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Initiates taxi payment.
    Tests monkeypatch ConsultationUseCase.handle, so gateway is not required.
    """
    try:
        uc = ConsultationUseCase(
            usage_repo=UsageRepository(db),
            gateway=None,  # patched in tests
        )

        tx_id = await uc.handle(
            user_id=current_user.uid,
            service="taxi",
            phone=req.phone,
            idempotency_key=x_idempotency_key,
        )

        reference = uuid.uuid4().hex.upper()
        expires_at = datetime.now(timezone.utc)

        return PaymentResponse(
            success=True,
            reference=reference,
            status=PaymentStatus.PENDING,
            expires_at=expires_at,
            message=f"transaction:{tx_id}",
            ussd_string=None,
        )

    except Exception:
        logger.exception(
            "Taxi payment failed for user=%s",
            getattr(current_user, "uid", None),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Taxi payment failed",
        )

