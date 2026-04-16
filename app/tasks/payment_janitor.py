import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import update, func, cast, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import AsyncSessionLocal
from app.models.payment import Payment, PaymentStatus

logger = logging.getLogger(__name__)

PAYMENT_EXPIRY_MINUTES = 15
VERIFICATION_STALE_HOURS = 24

async def expire_unconfirmed_payments():
    """
    Mark old pending payments as FAILED in bulk.
    Final Fix: Uses Python dict {} for JSONB casting to avoid 'scalar' errors
    and uses the Text class for the ARRAY type mapping.
    """
    async with AsyncSessionLocal() as session:
        try:
            now = datetime.now(timezone.utc)
            pending_cutoff = now - timedelta(minutes=PAYMENT_EXPIRY_MINUTES)
            stale_cutoff = now - timedelta(hours=VERIFICATION_STALE_HOURS)

            # Cast the column to JSONB once for use in jsonb_set
            json_as_jsonb = cast(Payment.metadata_json, JSONB)

            # Task 1: Cleanup PENDING
            stmt_pending = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.PENDING,
                    Payment.created_at < pending_cutoff
                )
                .values({
                    Payment.status: PaymentStatus.FAILED,
                    Payment.updated_at: now,
                    Payment.metadata_json: func.jsonb_set(
                        # Use a real Python dict {} so Postgres sees an OBJECT, not a string
                        func.coalesce(json_as_jsonb, cast({}, JSONB)),
                        cast(['expiry_reason'], ARRAY(Text)),
                        cast("ussd_timeout", JSONB)
                    )
                })
            )

            # Task 2: Cleanup AWAITING_VERIFICATION
            stmt_stale = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.AWAITING_VERIFICATION,
                    Payment.created_at < stale_cutoff
                )
                .values({
                    Payment.status: PaymentStatus.FAILED,
                    Payment.updated_at: now,
                    Payment.metadata_json: func.jsonb_set(
                        func.coalesce(json_as_jsonb, cast({}, JSONB)),
                        cast(['expiry_reason'], ARRAY(Text)),
                        cast("stale_verification", JSONB)
                    )
                })
            )

            res_p = await session.execute(stmt_pending)
            res_s = await session.execute(stmt_stale)
            await session.commit()

            p_rows = res_p.rowcount or 0
            s_rows = res_s.rowcount or 0

            if (p_rows + s_rows) > 0:
                logger.info(f"🧹 Janitor: Cleaned {p_rows} pending and {s_rows} stale payments.")

        except Exception as e:
            await session.rollback()
            logger.error(f"💥 Janitor failed: {str(e)}", exc_info=True)