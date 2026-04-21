from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.nurse_payment import NursePaymentRequest, NursePaymentResponse

class NursePaymentService:
    """
    Service to process nurse payments.
    Delegates payment logic to the core PaymentService.
    """

    # Centralized constant for category lookups
    CATEGORY = "nurse-services"

    @staticmethod
    async def process(db: AsyncSession, req: NursePaymentRequest) -> NursePaymentResponse:
        """
        Process a nurse payment by delegating to the unified PaymentService.
        """
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category=NursePaymentService.CATEGORY,
            req_data={
                "nurse_id": req.nurse_id,
                "service_type": req.service_type,
                "metadata": req.metadata
            }
        )

        return NursePaymentResponse(
            success=payment_result.success,
            transaction_id=payment_result.transaction_id,
            status=payment_result.status,
            message=payment_result.message
        )