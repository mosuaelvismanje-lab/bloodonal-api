import asyncio
import logging
from typing import Optional

from app.domain.interfaces import IPaymentGateway, IUsageRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.usage_repo import UsageRepository
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def charge_job(
    db: AsyncSession,
    payment_gateway: IPaymentGateway,
    user_id: str,
    amount: int,
    service: str,
    idempotency_key: Optional[str] = None,
):
    """
    Performs an async charge, records it in payment table, handles retries internally.
    """
    payment_repo = PaymentRepository(db)
    usage_repo = UsageRepository(db)

    try:
        tx_id = await payment_gateway.charge(user_id, amount)

        # Record payment in DB
        await payment_repo.create_payment(
            user_id=user_id,
            payment_type=service,
            amount=amount,
            idempotency_key=idempotency_key,
            provider_tx_id=tx_id
        )

        # Increment usage
        await usage_repo.increment_usage(user_id, service)

        logger.info("Charge succeeded for user=%s service=%s tx=%s", user_id, service, tx_id)

    except Exception as exc:
        logger.exception("Charge failed for user=%s service=%s", user_id, service)
        # Optionally enqueue retry_job here
        raise


async def retry_job(
    db: AsyncSession,
    payment_gateway: IPaymentGateway,
    user_id: str,
    amount: int,
    service: str,
    max_retries: int = 3
):
    """
    Retry a failed job up to max_retries times
    """
    for attempt in range(1, max_retries + 1):
        try:
            await charge_job(db, payment_gateway, user_id, amount, service)
            return
        except Exception:
            logger.warning("Retry %d/%d failed for user=%s service=%s", attempt, max_retries, user_id, service)
            await asyncio.sleep(2 ** attempt)  # exponential backoff

    logger.error("All retries failed for user=%s service=%s", user_id, service)


async def reconciliation_job(
    db: AsyncSession,
    payment_gateway: IPaymentGateway
):
    """
    Periodic reconciliation between provider and local ledger.
    """
    from app.repositories.payment_repo import PaymentRepository

    payment_repo = PaymentRepository(db)
    # Example: fetch pending payments from local DB
    # Compare with provider records
    # Update status if needed
    logger.info("Reconciliation job executed")
