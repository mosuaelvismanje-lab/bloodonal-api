# app/services/blood_request_payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.blood_payment import BloodRequestPaymentRequest, BloodRequestPaymentResponse


class BloodRequestPaymentService:
    """
    Service to process blood request payments.
    Delegates actual payment processing to PaymentService.
    """

    @staticmethod
    async def process(
        db: AsyncSession,
        req: BloodRequestPaymentRequest
    ) -> BloodRequestPaymentResponse:
        """
        Process a blood request payment.

        Args:
            db: Async SQLAlchemy session.
            req: BloodRequestPaymentRequest containing user_id, blood_group, quantity_bags, hospital_id, and optional metadata.

        Returns:
            BloodRequestPaymentResponse with success, transaction_id, status, and message.
        """

        # Call the generic PaymentService
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category="blood_request",
            req_data={
                "blood_group": req.blood_group,
                "quantity_bags": req.quantity_bags,
                "hospital_id": req.hospital_id,
                "metadata": req.metadata
            }
        )

        # Map generic PaymentResponse to BloodRequestPaymentResponse
        return BloodRequestPaymentResponse(
            success=payment_result.success,
            transaction_id=payment_result.transaction_id,
            status=payment_result.status,
            message=payment_result.message
        )
