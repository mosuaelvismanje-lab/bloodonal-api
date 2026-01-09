from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.bike_payment import BikePaymentRequest, BikePaymentResponse

class BikePaymentService: # ✅ Renamed from BikerPaymentService
    """
    Service to process bike payments.
    Delegates actual payment processing to PaymentService.
    """

    @staticmethod
    async def process(
        db: AsyncSession,
        req: BikePaymentRequest,
        user_id: str # ✅ Added user_id as an argument since it's not in the request body anymore
    ) -> BikePaymentResponse:
        """
        Process a bike payment.
        """

        # ✅ FIX: Use fields that actually exist in your new BikePaymentRequest
        # The new schema only has 'phone' and 'metadata'
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=user_id,
            category="biker",
            req_data={
                "phone": req.phone,
                "metadata": req.metadata
            }
        )

        # ✅ FIX: Map to the new BikePaymentResponse fields
        # (reference instead of transaction_id, and include expires_at)
        return BikePaymentResponse(
            success=payment_result.success,
            reference=payment_result.transaction_id or "N/A",
            status=payment_result.status,
            expires_at=payment_result.expires_at, # Ensure PaymentService returns this
            message=payment_result.message
        )
