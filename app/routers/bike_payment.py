import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
# ✅ UPDATE: Import the new specific bike schemas
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse, BikeFreeUsageResponse
# Keep PaymentStatus for logic consistency
from app.schemas.payment import PaymentStatus
from app.domain.usecases import ConsultationUseCase
from app.data.repositories import UsageRepository
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/payments/bike", tags=["payments"])


# -------------------------
# GET REMAINING FREE BIKE RIDES
# -------------------------
@router.get("/remaining", response_model=BikeFreeUsageResponse) # ✅ Updated response model
async def remaining_free_bike_rides(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db_session),
):
    """
    Fetch remaining free rides using the specific BikeFreeUsageResponse schema.
    """
    try:
        # Assuming UsageRepository has a count method
        used = await UsageRepository(db).count(user_id or "")
        free_limit = 0
        return BikeFreeUsageResponse(remaining=max(0, free_limit - used))
    except Exception:
        logger.exception("Error fetching remaining bike rides")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch remaining bike rides",
        )


# -------------------------
# PAY FOR BIKE RIDE
# -------------------------
@router.post("/", response_model=BikePaymentResponse) # ✅ Updated response model
async def pay_for_bike(
        req: BikePaymentRequest, # ✅ Updated request model (enforces 9-digit phone)
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
):
    """
    Initiate bike payment.
    Matches ConsultationUseCase(usage_repo, payment_gateway, call_gateway, chat_gateway)
    """
    try:
        # ✅ FIX: Match the 4-argument constructor in your usecase
        uc = ConsultationUseCase(
            usage_repo=UsageRepository(db),
            payment_gateway=None,
            call_gateway=None,
            chat_gateway=None
        )

        # ✅ Call handle with correct arguments
        tx_id = await uc.handle(
            user_id=current_user.uid,
            service="biker",
            phone=req.phone,
            idempotency_key=x_idempotency_key,
        )

        reference = uuid.uuid4().hex.upper()
        expires_at = datetime.now(timezone.utc)

        # ✅ Returns specifically structured BikePaymentResponse
        return BikePaymentResponse(
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


# -------------------------
# Export service aliases for central router / tests
# -------------------------
get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment
