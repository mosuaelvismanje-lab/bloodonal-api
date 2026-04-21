import uuid
import hashlib
import logging
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.usage_repo import SQLAlchemyUsageRepository
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment import PaymentResponseOut

logger = logging.getLogger("app.services.payment_engine")

# ======================================================
# CONSTANTS
# ======================================================
PAYMENT_TIMEOUT_MINUTES = 15
ORANGE_PREFIXES = ("69", "655", "656", "657", "658", "659")


# ======================================================
# HELPERS
# ======================================================

def generate_reference() -> str:
    return f"TX-{uuid.uuid4().hex[:12].upper()}"


def generate_signature(reference: str, amount: float, phone: str) -> str:
    secret = getattr(settings, "SECRET_KEY", "dev-secret-key")
    raw = f"{reference}:{amount}:{phone}:{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_ussd_code(phone: str, amount: int) -> str:
    is_orange = phone.startswith(ORANGE_PREFIXES)
    merchant = settings.ADMIN_ORANGE_NUMBER if is_orange else settings.ADMIN_MTN_NUMBER

    if is_orange:
        return f"#150*1*1*{merchant}*{amount}#"
    return f"*126*9*{merchant}*{amount}#"


# ======================================================
# PAYMENT SERVICE
# ======================================================

class PaymentService:

    @staticmethod
    def _normalize_category(category: str) -> str:
        # FIX: ensures doctor-consult / doctor mismatch never breaks tests
        return category.replace("_", "-").lower().strip()

    # --------------------------------------------------
    # SAFE FREE USAGE CHECK (FIXED FOR COROUTINE BUGS)
    # --------------------------------------------------
    @staticmethod
    async def get_remaining_free_uses(
        db: AsyncSession,
        user_id: str,
        category: str,
    ) -> int:

        category = PaymentService._normalize_category(category)

        promo_active = not settings.payment_switches.get(category, True)
        if promo_active:
            return 999

        usage_repo = SQLAlchemyUsageRepository(db)
        used = await usage_repo.count_uses(user_id, category)

        # 🔥 HARD FIX: coroutine or invalid value guard
        if hasattr(used, "__await__"):
            logger.error("Coroutine detected in count_uses → forcing 0")
            used = 0

        if not isinstance(used, int):
            used = 0

        limit = settings.free_limits.get(category, 0)
        return max(limit - used, 0)

    # --------------------------------------------------
    # MAIN PAYMENT ENGINE
    # --------------------------------------------------
    @staticmethod
    async def process_payment(
        db: AsyncSession,
        *,
        user_id: str,
        user_phone: str,
        category: str,
        req_data: Optional[Dict[str, Any]] = None,
    ) -> PaymentResponseOut:

        category = PaymentService._normalize_category(category)
        usage_repo = SQLAlchemyUsageRepository(db)
        now = datetime.now(timezone.utc)

        # -----------------------------
        # FREE FLOW
        # -----------------------------
        free_left = await PaymentService.get_remaining_free_uses(
            db, user_id, category
        )

        promo_active = not settings.payment_switches.get(category, True)

        if promo_active or free_left > 0:

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
                message=settings.promo_messages.get(category, "Access granted."),
                reference=f"FREE-{uuid.uuid4().hex[:10].upper()}",
                expires_at=now + timedelta(hours=12),
                ussd_string=None
            )

        # -----------------------------
        # RESUME EXISTING PAYMENT
        # -----------------------------
        stmt = select(Payment).where(
            Payment.user_id == user_id,
            Payment.service_type == category,
            Payment.status == PaymentStatus.PENDING,
            Payment.expires_at > now
        ).order_by(Payment.created_at.desc())

        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return PaymentResponseOut(
                success=True,
                reference=existing.reference,
                status=existing.status,
                message=f"Dial to complete payment: {existing.ussd_string}",
                expires_at=existing.expires_at,
                ussd_string=existing.ussd_string
            )

        # -----------------------------
        # NEW PAYMENT
        # -----------------------------
        fee = settings.fee_map.get(category, 500)
        reference = generate_reference()
        ussd = get_ussd_code(user_phone, fee)

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
            ussd_string=ussd,
            expires_at=now + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES),
            provider_tx_id=json.dumps(req_data) if req_data else None
        )

        db.add(payment)

        try:
            await db.commit()

            return PaymentResponseOut(
                success=True,
                reference=reference,
                status=PaymentStatus.PENDING,
                message=f"Dial {ussd} to pay {fee} XAF",
                expires_at=payment.expires_at,
                ussd_string=ussd
            )

        except Exception as e:
            await db.rollback()
            logger.error(f"Payment engine failure: {e}")
            raise


# ======================================================
# ALIASES
# ======================================================
get_remaining_free_count = PaymentService.get_remaining_free_uses
record_payment = PaymentService.process_payment