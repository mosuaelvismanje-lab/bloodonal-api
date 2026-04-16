import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import update, select, func
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import AsyncSessionLocal
from app.models.payment import Payment, PaymentStatus

# ✅ 2026 Timeouts: 15m for abandoned USSD | 24h for forgotten manual claims
PAYMENT_EXPIRY_MINUTES = 15
VERIFICATION_STALE_HOURS = 24

logger = logging.getLogger(__name__)


async def expire_unconfirmed_payments():
    """
    Efficiently marks old pending payments as FAILED in bulk.

    ✅ ATOMIC: Performs bulk updates via SQLAlchemy Core for speed.
    ✅ TRACEABLE: Updates JSONB metadata with expiry reasons for 2026 analytics.
    """
    async with AsyncSessionLocal() as session:
        try:
            now = datetime.now(timezone.utc)

            # 1. Define Cutoff Thresholds
            pending_cutoff = now - timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
            stale_cutoff = now - timedelta(hours=VERIFICATION_STALE_HOURS)

            # --- Task 1: Cleanup PENDING (Abandoned USSD) ---
            # We use .jsonb_set or metadata.concat to preserve existing metadata
            stmt_pending = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.PENDING,
                    Payment.created_at < pending_cutoff
                )
                .values(
                    status=PaymentStatus.FAILED,
                    updated_at=now,
                    # Tagging the reason for the Admin Dashboard
                    metadata=func.jsonb_set(
                        Payment.metadata,
                        '{expiry_reason}',
                        '"ussd_timeout"'
                    )
                )
            )

            # --- Task 2: Cleanup AWAITING_VERIFICATION (Stale Claims) ---
            stmt_stale = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.AWAITING_VERIFICATION,
                    Payment.created_at < stale_cutoff
                )
                .values(
                    status=PaymentStatus.FAILED,
                    updated_at=now,
                    metadata=func.jsonb_set(
                        Payment.metadata,
                        '{expiry_reason}',
                        '"stale_verification"'
                    )
                )
            )

            # Execute both updates
            res_p = await session.execute(stmt_pending)
            res_s = await session.execute(stmt_stale)

            await session.commit()

            # 2. Detailed Logging for Worker Monitoring
            total_affected = res_p.rowcount + res_s.rowcount
            if total_affected > 0:
                logger.info(
                    "🧹 [JANITOR] Cleanup Summary | Abandoned: %s | Stale Claims: %s | Total: %s",
                    res_p.rowcount, res_s.rowcount, total_affected
                )

        except SQLAlchemyError as e:
            await session.rollback()
            logger.error(f"💥 Database error during payment cleanup: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error in payment worker: {str(e)}")


# ---------------------------------------------------------
# NEW: Individual Service Cleanup (Hook for Orchestrator)
# ---------------------------------------------------------
async def fail_single_payment(reference: str, reason: str = "manual_cancel"):
    """
    Allows the API or Worker to manually expire a specific payment.
    Useful for 'Cancel' buttons in the UI.
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            update(Payment)
            .where(Payment.reference == reference)
            .values(
                status=PaymentStatus.FAILED,
                updated_at=datetime.now(timezone.utc),
                metadata=func.jsonb_set(Payment.metadata, '{expiry_reason}', f'"{reason}"')
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info(f"🚫 Payment {reference} manually failed. Reason: {reason}")