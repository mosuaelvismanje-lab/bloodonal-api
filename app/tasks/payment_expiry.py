from datetime import datetime, timedelta, timezone
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.db.session import AsyncSessionLocal
from app.models.payment import Payment, PaymentStatus

PAYMENT_EXPIRY_MINUTES = 10
logger = logging.getLogger(__name__)


async def expire_unconfirmed_payments():
    """
    Efficiently marks old pending payments as FAILED in bulk.
    Uses a single SQL UPDATE for scalability and audit safety.
    """
    async with AsyncSessionLocal() as session:
        try:
            # Timezone-aware (Python 3.12+ safe)
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(minutes=PAYMENT_EXPIRY_MINUTES)

            stmt = (
                update(Payment)
                .where(
                    Payment.status == PaymentStatus.PENDING,
                    Payment.created_at < cutoff
                )
                .values(
                    status=PaymentStatus.FAILED,
                    updated_at=now
                ) 
            )

            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount and result.rowcount > 0:
                logger.info(
                    "Expired %s unconfirmed payments", result.rowcount
                )

        except SQLAlchemyError as e:
            await session.rollback()
            logger.exception("Failed to expire payments")
            raise
