# app/services/biker_payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.biker_payment import BikerPaymentRequest, BikerPaymentResponse


class BikerPaymentService:
    """
    Service to process biker payments.
    Delegates actual payment processing to PaymentService.
    """

    @staticmethod
    async def process(
        db: AsyncSession,
        req: BikerPaymentRequest
    ) -> BikerPaymentResponse:
        """
        Process a biker payment.

        Args:
            db: Async SQLAlchemy session.
            req: BikerPaymentRequest containing user_id, biker_id, optional ride_distance_km, and metadata.

        Returns:
            BikerPaymentResponse with success, transaction_id, status, and message.
        """

        # Call the generic PaymentService
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category="biker",
            req_data={
                "biker_id": req.biker_id,
                "ride_distance_km": req.ride_distance_km,
                "metadata": req.metadata
            }
        )

        # Map generic PaymentResponse to BikerPaymentResponse
        return BikerPaymentResponse(
            success=payment_result.success,
            transaction_id=payment_result.transaction_id,
            status=payment_result.status,
            message=payment_result.message
        )
