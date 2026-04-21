import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.domain.usecases import SERVICE_FREE_LIMITS_SIMPLE as SERVICE_FREE_LIMITS
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponseOut,
    FreeUsageResponse,
    PaymentStatus,
)

from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payments/doctor-consults",
    tags=["doctor-payments"],
    redirect_slashes=False
)

# -------------------------------------------------
# ✅ FIXED: USE SERVICE (NOT REPO)
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_doctor_consults(
    user_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        target_uid = user_id or current_user.uid

        # 🔥 CRITICAL FIX: use service (this is what test mocks)
        remaining = await PaymentService.get_remaining_free_uses(
            user_id=target_uid,
            category="doctor"
        )

        return FreeUsageResponse(
            remaining=remaining,
            fee=2000 if remaining == 0 else 0
        )

    except Exception as e:
        logger.error(f"Doctor remaining error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining consults",
        )


# -------------------------------------------------
# PAY DOCTOR CONSULT
# -------------------------------------------------
@router.post("", response_model=PaymentResponseOut)
async def pay_doctor_consult(
    req: PaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    try:
        usage_repo = SQLAlchemyUsageRepository(db)

        used = await usage_repo.count_uses(current_user.uid, "doctor")
        free_limit = SERVICE_FREE_LIMITS.get("doctor", 0)

        # -------------------------------------------------
        # FREE FLOW
        # -------------------------------------------------
        if used < free_limit:
            ref = f"DOC-FREE-{uuid.uuid4().hex[:8].upper()}"

            await usage_repo.record_usage(
                user_id=current_user.uid,
                service="doctor",
                paid=False,
                amount=0.0,
                request_id=ref,
                idempotency_key=x_idempotency_key
            )

            await db.commit()

            return PaymentResponseOut(
                success=True,
                reference=ref,
                status=PaymentStatus.SUCCESS,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                message="Free doctor consultation granted.",
                ussd_string=None,
            )

        # -------------------------------------------------
        # PAID FLOW (SERVICE MUST BE CALLED)
        # -------------------------------------------------
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=current_user.uid,
            user_phone=req.phone,
            category="doctor",
        )

        await usage_repo.record_usage(
            user_id=current_user.uid,
            service="doctor",
            paid=True,
            amount=2000,
            request_id=payment_result.reference,
            idempotency_key=x_idempotency_key
        )

        await db.commit()

        return payment_result

    except Exception as exc:
        logger.exception("Doctor payment failed for user=%s", current_user.uid)
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )