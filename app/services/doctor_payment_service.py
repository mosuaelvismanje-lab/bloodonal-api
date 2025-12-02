# app/services/doctor_payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.payment import PaymentResponse, PaymentRequest


class DoctorPaymentService:

    @staticmethod
    async def process(db: AsyncSession, req: PaymentRequest) -> PaymentResponse:
        """
        Extend business rules for doctor payments.
        Example: weekend surcharge, specialty-specific fees, etc.
        """
        # Example custom rules
        # if req.metadata and req.metadata.get("weekend") == True:
        #     req.amount = 400

        return await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category="doctor",
            req=req
        )
