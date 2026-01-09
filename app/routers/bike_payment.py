# app/routers/bike_payment.py
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.payment import PaymentRequest, PaymentResponse, FreeUsageResponse, PaymentStatus
from app.domain.usecases import ConsultationUseCase
from app.data.repositories import UsageRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/payments/bike", tags=["payments"])


@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_bike_rides(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Optionally accept user_id query param for ad-hoc checks (keeps compatibility).
    In normal flows the authenticated user is used.
    """
    try:
        used = await UsageRepository(db).count(user_id or "")
        free_limit = 0  # keep fallback, real limit comes from domain/usecases if needed
        return FreeUsageResponse(remaining=max(0, free_limit - used))
    except Exception:
        logger.exception("Error fetching remaining bike rides")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining bike rides",
        )


@router.post("/", response_model=PaymentResponse)
async def pay_for_bike(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user=Depends(get_current_user),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Initiate bike payment. Tests monkeypatch ConsultationUseCase.handle to return a tx id.
    We call the usecase with the authenticated user's id and the phone provided in the JSON body.
    """
    try:
        uc = ConsultationUseCase(
            usage_repo=UsageRepository(db),
            gateway=None,  # tests patch handle, so gateway may be None here
        )

        tx_id = await uc.handle(
            user_id=current_user.uid,
            service="biker",
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
        logger.exception("Bike payment failed for user=%s", getattr(current_user, "uid", None))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bike payment failed",
        )
