from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.payment_admin import AdminConfirmPaymentRequest
from app.services.payment_confirmation import confirm_payment

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],  # Protect with admin auth later
)


@router.post("/confirm-payment")
async def admin_confirm_payment(
    payload: AdminConfirmPaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Admin manually confirms a payment after verifying SMS.
    """

    confirmed = await confirm_payment(
        db=db,
        transaction_id=payload.transaction_id,
        payer_phone=payload.payer_phone,
        provider=payload.provider,
        amount=payload.amount,
    )

    if not confirmed:
        raise HTTPException(
            status_code=404,
            detail="Payment not found, mismatched, or already confirmed",
        )

    return {
        "status": "confirmed",
        "transaction_id": payload.transaction_id,
    }
