from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.taxi_payment import TaxiPaymentRequest, TaxiPaymentResponse
import logging

logger = logging.getLogger(__name__)


class TaxiPaymentService:
    """
    Service to process taxi payments and track free ride usage.
    Delegates actual payment processing to the central PaymentService engine.
    """

    CATEGORY = "taxi"
    FREE_LIMIT = 5

    @staticmethod
    async def get_remaining_free_uses(db: AsyncSession, user_id: str) -> int:
        """
        Calculates remaining free rides.
        Returns an integer. Must be awaited in the router layer.
        """
        try:
            # PaymentService.get_usage_count is async; must be awaited
            used = await PaymentService.get_usage_count(
                db=db,
                user_id=user_id,
                category=TaxiPaymentService.CATEGORY
            )

            # Ensure used is treated as an int
            remaining = max(0, TaxiPaymentService.FREE_LIMIT - int(used))
            logger.info(f"Taxi free usage: user={user_id}, remaining={remaining}")
            return remaining

        except Exception as e:
            logger.error(f"Error calculating taxi usage for {user_id}: {e}")
            return 0

    @staticmethod
    async def process(
            db: AsyncSession,
            user_id: str,
            req: TaxiPaymentRequest
    ) -> TaxiPaymentResponse:
        """Processes the payment via the unified engine."""
        try:
            payment_result = await PaymentService.process_payment(
                db=db,
                user_id=user_id,
                phone=req.phone,
                amount=req.amount,
                category=TaxiPaymentService.CATEGORY,
                description=f"Taxi ride: {req.taxi_driver_id}",
                metadata={
                    "taxi_driver_id": req.taxi_driver_id,
                    "ride_distance_km": req.ride_distance_km,
                    **(req.metadata or {})
                }
            )

            # Ensure we safely extract the USSD string from the generic response
            ussd = getattr(payment_result, "ussd_string", None)

            return TaxiPaymentResponse(
                success=payment_result.success,
                reference=payment_result.reference,
                status=payment_result.status,
                message=payment_result.message,
                ussd_string=ussd
            )
        except Exception as e:
            logger.error(f"Taxi payment processing failed for user {user_id}: {e}")
            # Re-raising is correct here to allow the router to trigger 500/400 responses
            raise e