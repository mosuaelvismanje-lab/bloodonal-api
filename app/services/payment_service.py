import asyncio
import uuid
import hashlib
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Standards-aligned Config & Repository
from app.config import settings
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentResponseOut

# ✅ Dedicated Finance Logger
logger = logging.getLogger("app.services.payment_engine")

# 2026 Constants
PAYMENT_TIMEOUT_MINUTES = 15
ORANGE_PREFIXES = ("69", "655", "656", "657", "658", "659")


# ======================================================
# HELPERS (SECURITY / USSD)
# ======================================================

def generate_reference() -> str:
    """Generates a high-entropy unique reference for transactions."""
    return f"TX-{uuid.uuid4().hex[:12].upper()}"


def generate_signature(reference: str, amount: float, phone: str) -> str:
    """Creates a cryptographic hash for transaction integrity."""
    # secret_key should be in your .env
    secret = getattr(settings, "SECRET_KEY", "dev-secret-key")
    raw = f"{reference}:{amount}:{phone}:{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_ussd_code(phone: str, amount: int) -> str:
    """Generates provider-specific USSD for Cameroon (Orange/MTN)."""
    is_orange = phone.startswith(ORANGE_PREFIXES)
    merchant = settings.ADMIN_ORANGE_NUMBER if is_orange else settings.ADMIN_MTN_NUMBER

    if is_orange:
        return f"#150*1*1*{merchant}*{amount}#"
    return f"*126*9*{merchant}*{amount}#"


# ======================================================
# MASTER PAYMENT SERVICE
# ======================================================

class PaymentService:
    """
    The Unified Quota & Financial Engine.
    Orchestrates access for Blood Requests, Consultations, and Oxygen.
    """

    @staticmethod
    async def get_remaining_free_uses(
            db: AsyncSession,
            user_id: str,
            category: str,
    ) -> int:
        """Evaluates remaining quota vs global promo state."""
        category = category.replace("_", "-").lower()

        # 1. Global Promo Check
        promo_active = not settings.payment_switches.get(category, True)
        if promo_active:
            logger.debug(f"PROMO_ACTIVE: Unlimited access for {category}")
            return 999

            # 2. Database Usage Lookup
        usage_repo = SQLAlchemyUsageRepository(db)
        used = await usage_repo.count_uses(user_id, category) or 0

        # 3. Dynamic Limit Lookup
        limit = settings.free_limits.get(category, 0)
        return max(limit - used, 0)

    @staticmethod
    async def process_payment(
            db: AsyncSession,
            *,
            user_id: str,
            user_phone: str,
            category: str,
            req_data: Optional[Dict[str, Any]] = None,
    ) -> PaymentResponseOut:
        """
        Processes access requests.
        Returns either a Success (Free) or USSD payload (Paid).
        """
        category = category.replace("_", "-").lower()
        usage_repo = SQLAlchemyUsageRepository(db)
        now = datetime.now(timezone.utc)

        # 1. VALIDATE ACCESS RIGHTS
        free_left = await PaymentService.get_remaining_free_uses(db, user_id, category)
        promo_active = not settings.payment_switches.get(category, True)

        if promo_active or free_left > 0:
            logger.info(f"✅ [FREE_ACCESS] User: {user_id} | Category: {category}")

            await usage_repo.record_usage(
                user_id=user_id,
                service=category,
                paid=False,
                amount=0.0,
                idempotency_key=f"FREE-{uuid.uuid4().hex[:12]}"
            )
            await db.commit()

            return PaymentResponseOut(
                success=True,
                status=PaymentStatus.SUCCESS,
                message=settings.promo_messages.get(category, "Service granted."),
                reference=f"FREE-{uuid.uuid4().hex[:10].upper()}",
                expires_at=now + timedelta(hours=12),
                ussd_string=None
            )

        # 2. PAID FLOW - IDEMPOTENCY & STALE CLEANUP
        # Check for active pending transaction
        stmt = select(Payment).where(
            Payment.user_id == user_id,
            Payment.service_type == category,
            Payment.status == PaymentStatus.PENDING,
            Payment.expires_at > now
        ).order_by(Payment.created_at.desc()).limit(1)

        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"🔁 [RESUMING] Ref: {existing.reference}")
            return PaymentResponseOut(
                success=True,
                reference=existing.reference,
                status=existing.status,
                message=f"Finish payment: Dial {existing.ussd_string}",
                expires_at=existing.expires_at,
                ussd_string=existing.ussd_string
            )

        # 3. CREATE NEW TRANSACTION
        fee = settings.fee_map.get(category, 500)
        reference = generate_reference()
        ussd_code = get_ussd_code(user_phone, fee)

        # Merge request metadata for auditing
        meta_payload = req_data if req_data else {}

        payment = Payment(
            reference=reference,
            user_id=user_id,
            user_phone=user_phone,
            service_type=category,
            amount=float(fee),
            currency="XAF",
            provider="ORANGE" if user_phone.startswith(ORANGE_PREFIXES) else "MTN",
            signature=generate_signature(reference, fee, user_phone),
            status=PaymentStatus.PENDING,
            idempotency_key=reference,
            ussd_string=ussd_code,
            expires_at=now + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES),
            # Optional: JSON storage if your model supports it
            # provider_tx_id=json.dumps(meta_payload)
        )

        db.add(payment)

        try:
            await db.commit()
            logger.info(f"💳 [USSD_SENT] User: {user_id} | Code: {ussd_code}")

            return PaymentResponseOut(
                success=True,
                reference=reference,
                status=PaymentStatus.PENDING,
                message=f"Quota reached. Dial {ussd_code} to pay {fee} XAF",
                expires_at=payment.expires_at,
                ussd_string=ussd_code
            )
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ [ENGINE_FAILURE] {str(e)}")
            raise


# ======================================================
# ALIASES
# ======================================================
get_remaining_free_count = PaymentService.get_remaining_free_uses
record_payment = PaymentService.process_payment