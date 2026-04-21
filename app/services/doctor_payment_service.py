from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.doctor_payment import DoctorPaymentRequest, DoctorPaymentResponse


class DoctorPaymentService:
    """
    Service to process doctor payments.
    Delegates actual payment processing to PaymentService.
    """

    CATEGORY = "doctor"

    @staticmethod
    async def process(
        db: AsyncSession,
        req: DoctorPaymentRequest
    ) -> DoctorPaymentResponse:

        # -------------------------------------------------
        # SAFETY: normalize metadata
        # -------------------------------------------------
        metadata = req.metadata or {}

        # -------------------------------------------------
        # CORE PAYMENT ENGINE CALL
        # -------------------------------------------------
        payment_result = await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            user_phone=req.user_phone,
            category=DoctorPaymentService.CATEGORY,
            req_data={
                "doctor_id": req.doctor_id,
                "service_type": req.service_type,
                "metadata": metadata
            }
        )

        # -------------------------------------------------
        # HARD SAFETY: prevent coroutine / None leaks
        # -------------------------------------------------
        if hasattr(payment_result, "__await__"):
            raise RuntimeError("PaymentService returned coroutine instead of result")

        # -------------------------------------------------
        # NORMALIZE RESPONSE ID FIELD
        # -------------------------------------------------
        transaction_id = (
            getattr(payment_result, "reference", None)
            or getattr(payment_result, "transaction_id", None)
        )

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------
        return DoctorPaymentResponse(
            success=bool(payment_result.success),
            transaction_id=transaction_id,
            status=payment_result.status,
            message=payment_result.message
        )