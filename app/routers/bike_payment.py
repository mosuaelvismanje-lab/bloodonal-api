import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db_session
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse, BikeFreeUsageResponse
from app.schemas.payment import PaymentStatus
from app.domain.usecases import ConsultationUseCase
from app.data.repositories import UsageRepository
from app.services.payment_service import PaymentService
from app.domain.consultation_models import ChannelType, UserRoles

# -------------------------
# Logger Configuration
# -------------------------
logger = logging.getLogger(__name__)

# -------------------------
# Router Configuration
# -------------------------
router = APIRouter(
    prefix="/payments/bike",
    tags=["payments"],
    redirect_slashes=False
)


# -------------------------
# GET REMAINING FREE BIKE RIDES
# -------------------------
@router.get("/remaining", response_model=BikeFreeUsageResponse)
async def remaining_free_bike_rides(
        user_id: Optional[str] = None,
        db: AsyncSession = Depends(get_db_session),
):
    """
    Check remaining free bike rides for a user.
    """
    try:
        # ✅ FIX: Added "bike" as the second positional argument (service)
        # to match the UsageRepository.count() signature
        repo = UsageRepository(db)
        used = await repo.count(user_id or "", "bike")

        # Define your business logic for free limits here
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
@router.post("", response_model=BikePaymentResponse)
async def pay_for_bike(
        req: BikePaymentRequest,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiate bike payment via ConsultationUseCase.
    """
    try:
        uc = ConsultationUseCase(
            UsageRepository(db),
            None,  # payment_gateway
            None,  # call_gateway
            None  # chat_gateway
        )

        result = await uc.handle(
            caller_id=current_user.uid,
            recipient_id="BIKE_SERVICE_PROVIDER",
            caller_phone=req.phone,
            channel=ChannelType.VOICE,
            recipient_role=UserRoles.DOCTOR,
            idempotency_key=x_idempotency_key,
        )

        tx_id = getattr(result, 'transaction_id', result)

        return BikePaymentResponse(
            success=True,
            reference=uuid.uuid4().hex.upper(),
            status=PaymentStatus.PENDING,
            expires_at=datetime.now(timezone.utc),
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
# Service Aliases
# -------------------------
get_remaining_free_uses = PaymentService.get_remaining_free_uses
process_payment = PaymentService.process_payment
