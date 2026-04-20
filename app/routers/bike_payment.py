import logging
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Project Dependencies
from app.api.dependencies import get_current_user, get_db
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse, BikeFreeUsageResponse
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payments/bike",
    tags=["BikePayments"],
    redirect_slashes=False
)


# -------------------------
# GET REMAINING FREE BIKE RIDES
# -------------------------
@router.get("/remaining", response_model=BikeFreeUsageResponse)
async def remaining_free_bike_rides(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
):
    """
    Check remaining free bike rides via the Payment Engine.
    """
    try:
        # ✅ ALIGNED: Delegate to the Engine
        remaining = await PaymentService.get_remaining_free_uses(
            db,
            user_id=current_user.uid,
            category="bike"
        )

        return BikeFreeUsageResponse(
            remaining=remaining,
            fee=500 if remaining == 0 else 0
        )
    except Exception as e:
        logger.error(f"Error fetching bike rides for {current_user.uid}: {e}")
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
        db: AsyncSession = Depends(get_db),
        current_user=Depends(get_current_user),
        x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
):
    """
    Initiate bike payment or consume free ride via the Payment Engine.
    """
    try:
        # ✅ ALIGNED: Delegate the entire process to the Payment Engine
        payment_out = await PaymentService.process_payment(
            db,
            user_id=current_user.uid,
            user_phone=req.phone,
            category="bike",
            req_data=req.metadata if hasattr(req, 'metadata') else {}
        )

        # Map the generic PaymentResponseOut to your specific BikePaymentResponse
        return BikePaymentResponse(
            success=payment_out.success,
            reference=payment_out.reference,
            status=payment_out.status,
            expires_at=payment_out.expires_at,
            message=payment_out.message,
            ussd_string=payment_out.ussd_string
        )

    except Exception:
        logger.exception("Bike payment failed for user=%s", current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bike payment failed",
        )