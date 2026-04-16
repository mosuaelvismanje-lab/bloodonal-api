#app/services/payment_confirmation
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Model Imports
from app.models.payment import Payment, PaymentStatus
from app.models.wallet import Wallet
from app.models.usage_counter import UsageCounter
from app.data.models import Usage

logger = logging.getLogger(__name__)

# =====================================================================
# 1. CONFIRM PAYMENT (Credit Logic)
# =====================================================================
async def confirm_payment(
        db: AsyncSession,
        reference: str,
        transaction_id: str = None,
        payer_phone: str = None,
        provider: str = "MTN",
        amount: float = None
) -> bool:
    """
    Processes manual or automatic payment confirmation.
    Credits wallet, unlocks usage, and increments quotas.
    Uses 'with_for_update' to prevent race conditions during balance updates.
    """
    try:
        # 1️⃣ Fetch payment with the internal reference
        result = await db.execute(select(Payment).where(Payment.reference == reference))
        payment = result.scalar_one_or_none()

        if not payment:
            logger.warning(f"❌ Payment reference {reference} not found.")
            return False

        # 2️⃣ Idempotency check: Don't process twice
        if payment.status == PaymentStatus.SUCCESS:
            logger.info(f"ℹ️ Payment {reference} already confirmed.")
            return True

        # 3️⃣ Update Payment Record metadata
        payment.status = PaymentStatus.SUCCESS
        payment.confirmed_at = datetime.now(timezone.utc)

        if transaction_id: payment.provider_tx_id = transaction_id
        if payer_phone: payment.user_phone = payer_phone
        if amount: payment.amount = amount
        if provider: payment.provider = provider

        # 4️⃣ Credit User Wallet (Atomic Lock)
        # ✅ 'with_for_update' prevents multiple workers from updating the same wallet simultaneously
        wallet_stmt = select(Wallet).where(Wallet.user_id == payment.user_id).with_for_update()
        wallet_result = await db.execute(wallet_stmt)
        wallet = wallet_result.scalar_one_or_none()

        if not wallet:
            logger.info(f"👛 Creating new wallet for user: {payment.user_id}")
            wallet = Wallet(user_id=payment.user_id, balance=0.0)
            db.add(wallet)

        wallet.balance = float(wallet.balance) + float(payment.amount)

        # 5️⃣ Sync with Transaction Log (Usage)
        await db.execute(
            update(Usage)
            .where(Usage.transaction_id == reference)
            .values(paid=True)
        )

        # 6️⃣ Increment Quota (UsageCounter)
        # This assumes the record already exists from the initial request stage
        await db.execute(
            update(UsageCounter)
            .where(UsageCounter.user_id == payment.user_id)
            .where(UsageCounter.service == payment.service_type)
            .values(used=UsageCounter.used + 1)
        )

        await db.commit()
        logger.info(f"✅ Payment {reference} SUCCESS. Wallet credited. TxID: {transaction_id}")
        return True

    except Exception as e:
        logger.error(f"💥 Confirmation error {reference}: {str(e)}")
        await db.rollback()
        return False


# =====================================================================
# 2. REFUND PAYMENT (Reversal Logic)
# =====================================================================


async def refund_payment(
        db: AsyncSession,
        reference: str
) -> bool:
    """
    Reverses a confirmed payment.
    Deducts wallet, locks usage, and decrements quotas safely.
    """
    try:
        # 1️⃣ Fetch payment
        result = await db.execute(select(Payment).where(Payment.reference == reference))
        payment = result.scalar_one_or_none()

        if not payment or payment.status != PaymentStatus.SUCCESS:
            logger.warning(f"❌ Cannot refund {reference}: Payment not in SUCCESS status.")
            return False

        # 2️⃣ Update Payment Record Status
        # Check if 'REFUNDED' exists in your PaymentStatus Enum, fallback to FAILED
        refund_status = getattr(PaymentStatus, "REFUNDED", PaymentStatus.FAILED)
        payment.status = refund_status

        # 3️⃣ Deduct from Wallet (Locked for safety)
        wallet_stmt = select(Wallet).where(Wallet.user_id == payment.user_id).with_for_update()
        wallet_result = await db.execute(wallet_stmt)
        wallet = wallet_result.scalar_one_or_none()

        if wallet:
            # ✅ Ensure balance never drops below zero using func.greatest
            wallet.balance = func.greatest(0.0, float(wallet.balance) - float(payment.amount))

        # 4️⃣ Lock the Transaction Log (Usage)
        await db.execute(
            update(Usage)
            .where(Usage.transaction_id == reference)
            .values(paid=False)
        )

        # 5️⃣ Decrement Quota (UsageCounter)
        # ✅ Using func.greatest for Postgres compatibility (scalar comparison)
        await db.execute(
            update(UsageCounter)
            .where(UsageCounter.user_id == payment.user_id)
            .where(UsageCounter.service == payment.service_type)
            .values(used=func.greatest(0, UsageCounter.used - 1))
        )

        await db.commit()
        logger.info(f"⏪ Refund successful for {reference}. Wallet deducted.")
        return True

    except Exception as e:
        logger.error(f"💥 Refund error {reference}: {str(e)}")
        await db.rollback()
        return False