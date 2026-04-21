import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.payment_service import PaymentService
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse

logger = logging.getLogger(__name__)


class BikePaymentService:
    """
    Service to process bike payments.
    Delegates quota validation + USSD/payment logic to PaymentService.
    """

    CATEGORY = "bike"

    @staticmethod
    async def process(
        db: AsyncSession,
        req: BikePaymentRequest,
        user_id: str
    ) -> BikePaymentResponse:
        """
        Process a bike payment via the unified PaymentService.
        """

        try:
            payment_result = await PaymentService.process_payment(
                db=db,
                user_id=user_id,
                category=BikePaymentService.CATEGORY,
                req_data={
                    "phone": req.phone,
                    "metadata": getattr(req, "metadata", None)
                }
            )

            return BikePaymentResponse(
                success=payment_result.success,
                reference=payment_result.reference,
                status=payment_result.status,
                expires_at=payment_result.expires_at,
                message=payment_result.message,
                ussd_string=payment_result.ussd_string
            )

        except Exception:
            logger.exception(
                "BikePaymentService failed | user=%s | category=%s",
                user_id,
                BikePaymentService.CATEGORY
            )
            raise
