# app/services/blood_request_payment_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.payment_service import PaymentService
from app.schemas.payment import PaymentRequest, PaymentResponse


class BloodRequestPaymentService:

    @staticmethod
    async def process(db: AsyncSession, req: PaymentRequest) -> PaymentResponse:
        return await PaymentService.process_payment(
            db=db,
            user_id=req.user_id,
            category="blood_request",
            req=req
        )
