from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.payment import Payment, PaymentStatus
from app.models.wallet import Wallet

PAYMENT_CONFIRMATION_TIMEOUT_MINUTES = 10


async def confirm_payment(reference: str) -> bool:
    """
    Confirms a payment AFTER USSD completion (manual/admin/agent).
    Idempotent and safe.
    """

    async with AsyncSessionLocal() as session:
        # 1️⃣ Fetch payment
        result = await session.execute(
            select(Payment).where(Payment.idempotency_key == reference)
        )
        payment: Payment | None = result.scalar_one_or_none()

        if not payment:
            return False

        # 2️⃣ Idempotency check
        if payment.status == PaymentStatus.SUCCESS:
            return True  # already confirmed

        # 3️⃣ Timeout protection
        if datetime.utcnow() - payment.created_at.replace(tzinfo=None) > timedelta(
            minutes=PAYMENT_CONFIRMATION_TIMEOUT_MINUTES
        ):
            payment.status = PaymentStatus.FAILED
            await session.commit()
            return False

        # 4️⃣ Mark payment as SUCCESS
        payment.status = PaymentStatus.SUCCESS
        payment.updated_at = datetime.utcnow()

        # 5️⃣ Credit wallet (safe)
        wallet = await session.get(Wallet, payment.user_id)
        if not wallet:
            wallet = Wallet(user_phone=payment.user_id, balance=0)
            session.add(wallet)

        wallet.balance += int(payment.amount)

        await session.commit()
        return True
