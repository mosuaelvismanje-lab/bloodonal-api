from __future__ import annotations

from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session

from app.db.database import get_db
from .service import WalletService

router = APIRouter(prefix="/wallet", tags=["Wallet"])
service = WalletService()


# =========================================================
# WALLET SUMMARY
# =========================================================
@router.get("/summary/{owner_id}")
def get_wallet_summary(
    owner_id: UUID,
    owner_type: str = Query(..., description="DONOR or HOSPITAL"),
    db: Session = Depends(get_db),
):
    return service.get_wallet_summary(db, owner_id, owner_type)


# =========================================================
# CREDIT (ADMIN / TESTING / INTERNAL)
# =========================================================
@router.post("/credit/{owner_id}")
def credit_wallet(
    owner_id: UUID,
    owner_type: str = Body(...),
    amount: float = Body(...),
    reference_id: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    return service.credit_wallet(
        db=db,
        owner_id=owner_id,
        owner_type=owner_type,
        amount=amount,
        reference_id=reference_id,
        description=description,
    )


# =========================================================
# DEBIT
# =========================================================
@router.post("/debit/{owner_id}")
def debit_wallet(
    owner_id: UUID,
    owner_type: str = Body(...),
    amount: float = Body(...),
    reference_id: Optional[str] = Body(None),
    description: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    return service.debit_wallet(
        db=db,
        owner_id=owner_id,
        owner_type=owner_type,
        amount=amount,
        reference_id=reference_id,
        description=description,
    )


# =========================================================
# MOBILE MONEY VERIFICATION (CORE FEATURE 🔥)
# =========================================================
@router.post("/verify-payment")
def verify_mobile_money_payment(
    owner_id: UUID = Body(...),
    owner_type: str = Body(...),
    amount: float = Body(...),
    transaction_id: str = Body(...),
    payment_code: str = Body(...),  # e.g. a356s
    sms_text: str = Body(...),  # full SMS content
    db: Session = Depends(get_db),
):
    """
    This is your MOST IMPORTANT endpoints.

    Flow:
    1. User sends money via MoMo with payment_code in reason
    2. App reads SMS
    3. Frontend sends SMS + transaction_id + code here
    4. Backend verifies:
        - transaction_id not used before
        - payment_code matches pending request
        - amount matches expected
    5. If valid → CREDIT WALLET
    """

    # 🔐 Step 1: Prevent double payment
    existing = service.repo.get_transaction_by_reference(db, transaction_id)
    if existing:
        return {
            "status": "duplicate",
            "message": "Transaction already processed",
        }

    # 🔍 Step 2: Validate SMS contains payment code
    if payment_code not in sms_text:
        return {
            "status": "failed",
            "message": "Payment code not found in SMS",
        }

    # 🔍 Step 3: Validate amount appears in SMS (basic check)
    if str(int(amount)) not in sms_text:
        return {
            "status": "failed",
            "message": "Amount mismatch in SMS",
        }

    # ✅ Step 4: Credit wallet
    result = service.credit_wallet(
        db=db,
        owner_id=owner_id,
        owner_type=owner_type,
        amount=amount,
        reference_id=transaction_id,
        description=f"MoMo Payment [{payment_code}]",
        tx_type="CREDIT",
    )

    return {
        "status": "success",
        "message": "Payment verified and wallet credited",
        "data": result,
    }


# =========================================================
# PAYOUT REQUEST
# =========================================================
@router.post("/payout/request/{owner_id}")
def request_payout(
    owner_id: UUID,
    owner_type: str = Body(...),
    amount: float = Body(...),
    method: str = Body(...),
    account_number: str = Body(...),
    account_name: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    return service.request_payout(
        db=db,
        owner_id=owner_id,
        owner_type=owner_type,
        amount=amount,
        method=method,
        account_number=account_number,
        account_name=account_name,
    )


# =========================================================
# APPROVE PAYOUT (ADMIN)
# =========================================================
@router.post("/payout/approve/{payout_id}")
def approve_payout(
    payout_id: UUID,
    db: Session = Depends(get_db),
):
    return service.approve_payout(db, payout_id)


# =========================================================
# REJECT PAYOUT (ADMIN)
# =========================================================
@router.post("/payout/reject/{payout_id}")
def reject_payout(
    payout_id: UUID,
    reason: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    return service.reject_payout(db, payout_id, reason)


# =========================================================
# TRANSACTION HISTORY
# =========================================================
@router.get("/transactions/{owner_id}")
def list_transactions(
    owner_id: UUID,
    owner_type: str = Query(...),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    return service.list_transactions(db, owner_id, owner_type, limit)


# =========================================================
# PAYOUT HISTORY
# =========================================================
@router.get("/payouts/{owner_id}")
def list_payouts(
    owner_id: UUID,
    owner_type: str = Query(...),
    db: Session = Depends(get_db),
):
    return service.list_payouts(db, owner_id, owner_type)


# =========================================================
# BILLING
# =========================================================
@router.post("/billing/create")
def create_billing(
    hospital_id: UUID = Body(...),
    amount: float = Body(...),
    billing_type: str = Body(...),
    reference_id: Optional[str] = Body(None),
    db: Session = Depends(get_db),
):
    return service.create_billing(
        db=db,
        hospital_id=hospital_id,
        amount=amount,
        billing_type=billing_type,
        reference_id=reference_id,
    )


@router.post("/billing/pay/{billing_id}")
def mark_billing_paid(
    billing_id: UUID,
    db: Session = Depends(get_db),
):
    return service.mark_billing_paid(db, billing_id)


@router.get("/billing/{hospital_id}")
def list_billings(
    hospital_id: UUID,
    db: Session = Depends(get_db),
):
    return service.list_billings(db, hospital_id)