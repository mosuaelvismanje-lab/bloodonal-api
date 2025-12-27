# app/services/taxi_payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.taxi_payment import TaxiPaymentRequest, TaxiPaymentResponse


class TaxiPaymentService:
    """
    Service to process taxi payments.
    Delegates actual payment processing to PaymentService.
    """

    @staticmethod
    async def process(
        db: AsyncSession,
        req: TaxiPaymentRequest
    ) -> TaxiPaymentResponse:
        """
        Process a taxi payment.

        Args:
            db: Async SQLAlchemy session.
            req: TaxiPaymentRequest containing user_id, taxi_driver_id, optional ride_distance_km, and optional metadata.

        Returns:
            TaxiPaymentResponse with success, transaction_id, status, and message.
        """

        # Call the generic PaymentService
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category="taxi",
            req_data={
                "taxi_driver_id": req.taxi_driver_id,
                "ride_distance_km": req.ride_distance_km,
                "metadata": req.metadata
            }
        )

        # Map generic PaymentResponse to TaxiPaymentResponse
        return TaxiPaymentResponse(
            success=payment_result.success,
            transaction_id=payment_result.transaction_id,
            status=payment_result.status,
            message=payment_result.message
        )
