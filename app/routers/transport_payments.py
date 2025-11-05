# app/routers/transport_payments.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.schemas.payment import PaymentRequest, PaymentResponse, FreeConsultsResponse
from app.services.payment_service import get_remaining_free_count, record_payment

FEE_AMOUNT = 500  # Default transport fee

router = APIRouter(prefix="/v1/payments", tags=["transport-payments"])


@router.get("/transports/remaining", response_model=FreeConsultsResponse)
def remaining_free_rides(user_id: str, db: Session = Depends(get_db)):
    """
    Returns the number of remaining free transport rides for the given user.
    """
    try:
        remaining = get_remaining_free_count(db, user_id, payment_type="transport")
        return FreeConsultsResponse(remaining=remaining)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not fetch remaining rides: {str(e)}"
        )


@router.post("/transport", response_model=PaymentResponse)
def pay_for_transport(req: PaymentRequest, db: Session = Depends(get_db)):
    """
    Processes a transport payment. Uses free rides first, otherwise charges FEE_AMOUNT.
    """
    try:
        free_rides_left = get_remaining_free_count(db, req.user_id, payment_type="transport")
        amount_to_charge = 0 if free_rides_left > 0 else FEE_AMOUNT

        tx_id = record_payment(
            db,
            req.user_id,
            payment_type="transport",
            amount=amount_to_charge
        )

        return PaymentResponse(success=True, transaction_id=tx_id)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process transport payment: {str(e)}"
        )
