from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import update, func, cast, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.modules.payment.models import PaymentStatus, Payment

logger = logging.getLogger(__name__)

# =========================================================
# CONFIG
# =========================================================
PAYMENT_EXPIRY_MINUTES: int = 15
VERIFICATION_STALE_HOURS: int = 24


# =========================================================
# INTERNAL HELPERS
# =========================================================
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _build_metadata_update(reason: str):
    """
    Safely build JSONB update expression.

    NOTE:
    - Uses jsonb_set
    - Avoids invalid casts like cast("string", JSONB)
    """
    return func.jsonb_set(
        func.coalesce(cast(Payment.metadata_json, JSONB), cast("{}", JSONB)),
        cast(["expiry_reason"], ARRAY(Text)),
        func.to_jsonb(reason),
        True,  # create missing
    )


# =========================================================
# MAIN TASK
# =========================================================
async def expire_unconfirmed_payments() -> Tuple[int, int]:
    """
    Bulk cleanup for expired payments.

    Returns:
        (pending_expired_count, stale_verification_count)

    Enterprise guarantees:
    - Atomic execution per batch
    - Safe rollback on failure
    - Resilient to DB/network interruptions
    - Structured logging for observability
    """

    async with AsyncSessionLocal() as session:  # type: AsyncSession
        try:
            now = _now_utc()

            pending_cutoff = now - timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
            stale_cutoff = now - timedelta(hours=VERIFICATION_STALE_HOURS)

            # -----------------------------
            # EXPIRE PENDING PAYMENTS
            # -----------------------------
            stmt_pending = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.PENDING,
                    Payment.created_at < pending_cutoff,
                )
                .values(
                    status=PaymentStatus.FAILED,
                    updated_at=now,
                    metadata_json=_build_metadata_update("ussd_timeout"),
                )
            )

            # -----------------------------
            # EXPIRE STALE VERIFICATIONS
            # -----------------------------
            stmt_stale = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.AWAITING_VERIFICATION,
                    Payment.created_at < stale_cutoff,
                )
                .values(
                    status=PaymentStatus.FAILED,
                    updated_at=now,
                    metadata_json=_build_metadata_update("stale_verification"),
                )
            )

            # -----------------------------
            # EXECUTION (RESILIENT BLOCK)
            # -----------------------------
            res_pending = await session.execute(stmt_pending)
            res_stale = await session.execute(stmt_stale)

            await session.commit()

            pending_count = int(res_pending.rowcount or 0)
            stale_count = int(res_stale.rowcount or 0)

            if pending_count or stale_count:
                logger.info(
                    "payment_janitor_cleanup",
                    extra={
                        "pending_expired": pending_count,
                        "stale_expired": stale_count,
                        "timestamp": now.isoformat(),
                    },
                )

            return pending_count, stale_count

        # -----------------------------
        # NETWORK / DB INSTABILITY
        # -----------------------------
        except (DBAPIError, ConnectionResetError) as exc:
            await session.rollback()

            logger.warning(
                "payment_janitor_connection_issue",
                extra={
                    "error": str(exc),
                    "action": "rollback",
                },
            )

            return 0, 0

        # -----------------------------
        # SQL ERRORS (LOGIC / QUERY)
        # -----------------------------
        except SQLAlchemyError as exc:
            await session.rollback()

            logger.error(
                "payment_janitor_sql_error",
                extra={
                    "error": str(exc),
                },
                exc_info=True,
            )

            raise

        # -----------------------------
        # UNKNOWN FAILURE
        # -----------------------------
        except Exception as exc:
            await session.rollback()

            logger.exception(
                "payment_janitor_unexpected_failure",
                extra={
                    "error": str(exc),
                },
            )

            raise