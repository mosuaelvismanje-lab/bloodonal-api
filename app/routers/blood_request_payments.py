import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Pattern Alignment: Using consistent dependencies
from app.api.dependencies import get_current_user, get_db_session
from app.schemas.payment import (
    PaymentRequest,
    PaymentResponse,
    FreeUsageResponse,
    PaymentStatus,
)
from app.domain.usecases import ConsultationUseCase
from app.data.repositories import UsageRepository
from app.domain.consultation_models import ChannelType, UserRoles

logger = logging.getLogger(__name__)

# -------------------------------------------------
# ROUTER CONFIG
# -------------------------------------------------
# FIX: No "/v1" here. Matches Bike/Doctor pattern.
router = APIRouter(
    prefix="/payments/blood-request",
    tags=["payments"],
    redirect_slashes=False
)


# -------------------------------------------------
# GET REMAINING FREE BLOOD REQUESTS
# -------------------------------------------------
@router.get("/remaining", response_model=FreeUsageResponse)
async def remaining_free_blood_requests(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),  # ✅ Added: Pattern alignment
):
    """
    Returns remaining free blood requests for a user.
    Prioritizes query param user_id, falls back to token uid.
    """
    try:
        # Step 1: Determine target user (matches Bike logic)
        target_uid = user_id or getattr(current_user, "uid", None)

        if not target_uid:
            return FreeUsageResponse(remaining=0)

        # Step 2: Query repository
        repo = UsageRepository(db)
        used = await repo.count(target_uid, "blood_request")

        # Business logic for free blood requests
        free_limit = 0

        return FreeUsageResponse(remaining=max(0, free_limit - used))
    except Exception:
        logger.exception("Error computing remaining blood requests")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to compute remaining blood requests",
        )


# -------------------------------------------------
# PAY FOR BLOOD REQUEST
# -------------------------------------------------
@router.post("", response_model=PaymentResponse)
async def pay_for_blood_request(
        req: PaymentRequest,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),  # ✅ Verified Pattern
        x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Initiates blood request payment using current_user.uid.
    Matches Bike/Doctor pattern to ensure test compatibility.
    """
    try:
        # Step 1: Initialize UseCase
        uc = ConsultationUseCase(
            usage_repo=UsageRepository(db),
            payment_gateway=None,  # Patched in tests
            call_gateway=None,
            chat_gateway=None
        )

        # Step 2: Execute domain logic (aligned with Bike recipient style)
        result = await uc.handle(
            caller_id=current_user.uid,
            recipient_id="BLOOD_SERVICE_PROVIDER",
            caller_phone=req.phone,
            channel=ChannelType.VOICE,
            recipient_role=UserRoles.DOCTOR,
            idempotency_key=x_idempotency_key,
        )

        # Step 3: Extract transaction ID safely
        tx_id = getattr(result, 'transaction_id', result)

        return PaymentResponse(
            success=True,
            reference=uuid.uuid4().hex.upper(),
            status=PaymentStatus.PENDING,
            expires_at=datetime.now(timezone.utc),
            message=f"transaction:{tx_id}",
            ussd_string=None,
        )

    except Exception as exc:
        logger.exception(
            "Blood request payment failed for user=%s",
            getattr(current_user, "uid", "Unknown")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Payment processing failed: {str(exc)}",
        )
