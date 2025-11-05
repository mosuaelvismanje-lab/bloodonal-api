# app/routers/payments.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import PaymentRequest, PaymentResponse, FreeConsultsResponse
from app.services.payment_service import get_remaining_free_count, record_payment  # make these async
from app.database import get_async_session

router = APIRouter(prefix="/v1/payments", tags=["blood-request-payments"])

@router.get("/blood-requests/remaining", response_model=FreeConsultsResponse)
async def remaining_free_requests(user_id: str, db: AsyncSession = Depends(get_async_session)):
    remaining = await get_remaining_free_count(db, user_id, payment_type="blood_request")
    return FreeConsultsResponse(remaining=remaining)

@router.post("/blood-request", response_model=PaymentResponse)
async def pay_for_blood_request(req: PaymentRequest, db: AsyncSession = Depends(get_async_session)):
    used = await get_remaining_free_count(db, req.user_id, payment_type="blood_request")
    amount = 0 if used > 0 else FEE_AMOUNT
    tx_id = await record_payment(db, req.user_id, payment_type="blood_request", amount=amount)
    return PaymentResponse(success=True, transaction_id=tx_id)
