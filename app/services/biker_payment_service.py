import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse

logger = logging.getLogger(__name__)

class BikePaymentService:
    """
    Service to process bike payments.
    Delegates actual payment processing logic (Quota check + USSD) to PaymentService.
    """

    @staticmethod
    async def process(
        db: AsyncSession,
        req: BikePaymentRequest,
        user_id: str
    ) -> BikePaymentResponse:
        """
        Process a bike payment by delegating to the unified PaymentService.
        """
        try:
            # 1. ✅ Delegate to the core PaymentService
            # We map the category to 'bike' to match your SERVICE_FREE_LIMITS keys.
            payment_result = await PaymentService.process_payment(
                db=db,
                user_id=user_id,
                category="bike",
                req_data={
                    "phone": req.phone,
                    "metadata": req.metadata
                }
            )

            # 2. ✅ Map the generic PaymentResponseOut to BikePaymentResponse
            # We ensure ussd_string is passed through so the Android UI knows to dial.
            return BikePaymentResponse(
                success=payment_result.success,
                reference=payment_result.reference,
                status=payment_result.status,
                expires_at=payment_result.expires_at,
                message=payment_result.message,
                ussd_string=payment_result.ussd_string
            )

        except Exception as e:
            logger.error(f"BikePaymentService failed for user {user_id}: {str(e)}")
            # We re-raise or handle locally depending on your preference,
            # but usually, we want the router to handle the HTTPException.
            raise e
