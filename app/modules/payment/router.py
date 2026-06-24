from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

# 🔗 Core dependencies
from app.api.dependencies import get_db_session, get_current_user

# 🔗 Models / Enums
from app.modules.payment.models import PaymentStatus

# 🔗 Services
from app.modules.payment.service import PaymentService
from app.modules.blood.wallet.repository import WalletRepository
from app.modules.blood.security.fraud_detection import FraudDetector

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


# =========================================================
# 🔐 AUTH GUARDS
# =========================================================
def require_user(user=Depends(get_current_user)):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_admin(user=Depends(get_current_user)):
    if not getattr(user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# =========================================================
# 🧩 SERVICE FACTORY (IMPORTANT)
# =========================================================
def get_payment_service(db: AsyncSession) -> PaymentService:
    """
    Centralized dependency builder.
    Ensures consistent wiring across endpoints.
    """
    wallet_repo = WalletRepository()
    fraud_detector = FraudDetector()

    return PaymentService(
        db=db,
        wallet_repo=wallet_repo,
        fraud_detector=fraud_detector,
    )


# =========================================================
# 💳 INITIATE PAYMENT
# =========================================================
@router.post("/initiate", response_model=Dict[str, Any])
async def initiate_payment(
        amount: float,
        phone: str,
        db: AsyncSession = Depends(get_db_session),
        user=Depends(require_user),
):
    """
    Step 1:
    - Backend generates reference (e.g a356s)
    - User sends MoMo with reference in "reason"
    """
    service = get_payment_service(db)

    try:
        return await service.initiate_payment(
            user_id=user.id,
            amount=amount,
            phone=phone,
        )

    except Exception as e:
        logger.exception("Payment initiation failed")
        raise HTTPException(
            status_code=500,
            detail="Payment initiation failed",
        ) from e


# =========================================================
# 📩 VERIFY PAYMENT (SMS MATCH)
# =========================================================
@router.post("/verify", response_model=Dict[str, Any])
async def verify_payment(
        transaction_id: str,
        message: str,
        db: AsyncSession = Depends(get_db_session),
        user=Depends(require_user),
):
    """
    Step 2:
    - App reads SMS
    - Sends:
        ✔ transaction_id
        ✔ full SMS message

    Backend extracts:
        ✔ reference
        ✔ amount
        ✔ phone
    """
    service = get_payment_service(db)

    try:
        return await service.verify_payment(
            user_id=user.id,
            transaction_id=transaction_id,
            sms_message=message,
        )

    except Exception as e:
        logger.exception("Payment verification failed")
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed",
        ) from e


# =========================================================
# 📄 GET USER PAYMENTS
# =========================================================
@router.get("/me", response_model=Dict[str, Any])
async def get_my_payments(
        status_filter: Optional[PaymentStatus] = Query(None),
        db: AsyncSession = Depends(get_db_session),
        user=Depends(require_user),
):
    service = get_payment_service(db)

    return await service.get_user_payments(
        user_id=user.id,
        status=status_filter,
    )


# =========================================================
# 🔍 GET SINGLE PAYMENT
# =========================================================
@router.get("/{payment_id}", response_model=Dict[str, Any])
async def get_payment(
        payment_id: UUID,
        db: AsyncSession = Depends(get_db_session),
        user=Depends(require_user),
):
    service = get_payment_service(db)

    payment = await service.get_payment(payment_id)

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # 🔒 Ownership / Admin check
    if payment["user_id"] != str(user.id) and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Forbidden")

    return payment


# =========================================================
# ❌ CANCEL PAYMENT
# =========================================================
@router.post("/{payment_id}/cancel", response_model=Dict[str, Any])
async def cancel_payment(
        payment_id: UUID,
        db: AsyncSession = Depends(get_db_session),
        user=Depends(require_user),
):
    service = get_payment_service(db)

    try:
        return await service.cancel_payment(
            payment_id=payment_id,
            user_id=user.id,
        )

    except Exception as e:
        logger.exception("Cancel payment failed")
        raise HTTPException(
            status_code=400,
            detail="Unable to cancel payment",
        ) from e


# =========================================================
# 🛠 ADMIN: LIST ALL PAYMENTS
# =========================================================
@router.get("/admin/all", response_model=Dict[str, Any])
async def admin_get_all_payments(
        limit: int = Query(50, le=200),
        offset: int = Query(0),
        db: AsyncSession = Depends(get_db_session),
        admin=Depends(require_admin),
):
    service = get_payment_service(db)

    return await service.get_all_payments(
        limit=limit,
        offset=offset,
    )


# =========================================================
# 🚨 ADMIN: FORCE VERIFY
# =========================================================
@router.post("/admin/{payment_id}/force-verify", response_model=Dict[str, Any])
async def admin_force_verify(
        payment_id: UUID,
        db: AsyncSession = Depends(get_db_session),
        admin=Depends(require_admin),
):
    """
    ⚠️ Use carefully
    Bypasses SMS verification
    """
    service = get_payment_service(db)

    try:
        return await service.force_verify(payment_id)

    except Exception as e:
        logger.exception("Force verify failed")
        raise HTTPException(
            status_code=400,
            detail="Force verification failed",
        ) from e


# =========================================================
# 🚨 ADMIN: BLOCK PAYMENT
# =========================================================
@router.post("/admin/{payment_id}/block", response_model=Dict[str, Any])
async def admin_block_payment(
        payment_id: UUID,
        reason: str,
        db: AsyncSession = Depends(get_db_session),
        admin=Depends(require_admin),
):
    service = get_payment_service(db)

    try:
        return await service.block_payment(
            payment_id=payment_id,
            reason=reason,
        )

    except Exception as e:
        logger.exception("Block payment failed")
        raise HTTPException(
            status_code=400,
            detail="Failed to block payment",
        ) from e


