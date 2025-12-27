# app/services/doctor_payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.doctor_payment import DoctorPaymentRequest, DoctorPaymentResponse


class DoctorPaymentService:
    """
    Service to process doctor payments with optional business rules.
    Delegates actual payment processing to PaymentService.
    """

    @staticmethod
    async def process(
        db: AsyncSession,
        req: DoctorPaymentRequest
    ) -> DoctorPaymentResponse:
        """
        Process a doctor payment.

        Args:
            db: Async SQLAlchemy session.
            req: DoctorPaymentRequest containing user_id, doctor_id, service_type, optional metadata.

        Returns:
            DoctorPaymentResponse with success, transaction_id, status, and message.
        """

        # Example custom business rules (optional):
        # if req.metadata and req.metadata.get("weekend") is True:
        #     amount = 400
        # else:
        #     amount = 300

        # Call the generic PaymentService
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category="doctor",
            req_data={
                "doctor_id": req.doctor_id,
                "service_type": req.service_type,
                "metadata": req.metadata
            }
        )

        # Map generic PaymentResponse to DoctorPaymentResponse
        return DoctorPaymentResponse(
            success=payment_result.success,
            transaction_id=payment_result.transaction_id,
            status=payment_result.status,
            message=payment_result.message
        )
