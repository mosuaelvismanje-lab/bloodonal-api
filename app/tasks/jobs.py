from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.interfaces import IPaymentGateway, IUsageRepository
from app.repositories.payment_repo import PaymentRepository
from app.repositories.usage_repo import UsageRepository

logger = logging.getLogger(__name__)

MAX_RETRY_BACKOFF_SECONDS = 30


def _validate_positive_int(value: int, field_name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return value


async def charge_job(
    db: AsyncSession,
    payment_gateway: IPaymentGateway,
    user_id: str,
    amount: int,
    service: str,
    idempotency_key: Optional[str] = None,
) -> str:
    """
    Perform an async charge and record the result in local storage.

    Enterprise rules:
    - Validate inputs early
    - Keep payment gateway charge and DB persistence together
    - Roll back the DB session on failure
    - Return provider transaction ID for observability
    """
    if not user_id or not str(user_id).strip():
        raise ValueError("user_id is required")

    _validate_positive_int(amount, "amount")

    service = str(service).strip()
    if not service:
        raise ValueError("service is required")

    payment_repo = PaymentRepository(db)
    usage_repo = UsageRepository(db)

    try:
        tx_id = await payment_gateway.charge(user_id, amount)

        await payment_repo.create_payment(
            user_id=user_id,
            payment_type=service,
            amount=amount,
            idempotency_key=idempotency_key,
            provider_tx_id=tx_id,
        )

        await usage_repo.increment_usage(user_id, service)

        await db.commit()

        logger.info(
            "charge_succeeded",
            extra={
                "user_id": user_id,
                "service": service,
                "amount": amount,
                "provider_tx_id": tx_id,
            },
        )
        return tx_id

    except Exception:
        await db.rollback()
        logger.exception(
            "charge_failed",
            extra={
                "user_id": user_id,
                "service": service,
                "amount": amount,
            },
        )
        raise


async def retry_job(
    db: AsyncSession,
    payment_gateway: IPaymentGateway,
    user_id: str,
    amount: int,
    service: str,
    max_retries: int = 3,
    idempotency_key: Optional[str] = None,
) -> Optional[str]:
    """
    Retry a failed charge job with exponential backoff.
    """
    _validate_positive_int(max_retries, "max_retries")

    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await charge_job(
                db=db,
                payment_gateway=payment_gateway,
                user_id=user_id,
                amount=amount,
                service=service,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "retry_failed",
                extra={
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "user_id": user_id,
                    "service": service,
                },
            )

            if attempt < max_retries:
                delay = min(2**attempt, MAX_RETRY_BACKOFF_SECONDS)
                await asyncio.sleep(delay)

    logger.error(
        "all_retries_failed",
        extra={
            "user_id": user_id,
            "service": service,
            "max_retries": max_retries,
        },
    )
    if last_exc:
        raise last_exc
    return None


async def reconciliation_job(db: AsyncSession, payment_gateway: IPaymentGateway) -> int:
    """
    Reconcile local payment records with provider state.

    This job is intentionally conservative:
    - It only attempts reconciliation if the repository exposes supported methods.
    - It does not invent provider state transitions.
    """
    payment_repo = PaymentRepository(db)
    reconciled_count = 0

    try:
        pending_getter = getattr(payment_repo, "get_pending_payments", None)
        reconcile_method = getattr(payment_repo, "reconcile_payment", None)

        if not callable(pending_getter):
            logger.info("reconciliation_skipped_no_pending_method")
            return 0

        pending_payments = await pending_getter()
        for payment in pending_payments or []:
            provider_tx_id = getattr(payment, "provider_tx_id", None)
            if not provider_tx_id:
                continue

            provider_status = await payment_gateway.verify_transaction(provider_tx_id)

            if callable(reconcile_method):
                await reconcile_method(payment, provider_status)
                reconciled_count += 1

        await db.commit()

        logger.info(
            "reconciliation_completed",
            extra={"reconciled_count": reconciled_count},
        )
        return reconciled_count

    except Exception:
        await db.rollback()
        logger.exception("reconciliation_failed")
        raise