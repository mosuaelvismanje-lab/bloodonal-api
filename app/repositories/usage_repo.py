import logging
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_counter import UsageCounter
from app.domain.interfaces import IUsageRepository
from app.config import settings
from app.services.registry import registry

logger = logging.getLogger(__name__)


class SQLAlchemyUsageRepository(IUsageRepository):
    """
    The Quota Gatekeeper: Manages atomic increments for user service usage.
    Ensures users stay within 'Free' limits and prevents double-billing via idempotency.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def count_uses(self, user_id: str, service: str) -> int:
        """
        Fetches current usage count.
        Uses the Registry to map 'service-name' to 'quota_type'.
        """
        meta = registry.get_service_meta(service)
        quota_type = meta["quota_type"]

        try:
            stmt = select(UsageCounter.used).where(
                UsageCounter.user_id == user_id,
                UsageCounter.service == quota_type
            )
            result = await self.session.execute(stmt)
            return result.scalar() or 0
        except Exception as e:
            logger.error(f"Error counting uses for {user_id}/{quota_type}: {e}")
            return 0

    async def record_usage(
            self,
            user_id: str,
            service: str,
            paid: bool,
            amount: float,
            transaction_id: Optional[str] = None,
            idempotency_key: Optional[str] = None,
            request_id: Optional[str] = None
    ) -> None:
        """
        Atomically increments usage using PG UPSERT.
        Includes a strict check to prevent double-counting on retries.
        """
        # 1. Resolve Metadata
        meta = registry.get_service_meta(service)
        quota_type = meta["quota_type"]

        # Registry-driven logic for payment enforcement
        # (Note: metadata key should match registry.py implementation)
        is_enabled = meta.get("is_enabled", True)

        if not is_enabled:
            logger.warning(f"Attempted usage for disabled service: {service}")
            return

        # 2. Idempotency Guard
        # Check if this specific transaction/activation has already been processed
        if idempotency_key:
            existing = await self.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"♻️ Duplicate request detected for key {idempotency_key}. Skipping increment.")
                return

        # 3. Prepare Atomic UPSERT
        stmt = insert(UsageCounter).values(
            user_id=user_id,
            service=quota_type,
            used=1,
            idempotency_key=idempotency_key,
            request_id=request_id
        )

        # Atomic increment on conflict.
        # We update the 'used' count and record the latest keys.
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=['user_id', 'service'],
            set_={
                "used": UsageCounter.used + 1,
                "idempotency_key": idempotency_key,
                "request_id": request_id
            }
        )

        try:
            await self.session.execute(upsert_stmt)
            logger.info(f"📈 Quota '{quota_type}' updated for {user_id}. Key: {idempotency_key}")
        except Exception as e:
            logger.error(f"💥 Critical: Failed to record usage for {user_id}: {e}")
            # We raise so the Orchestrator can rollback the whole transaction
            raise RuntimeError(f"Database error during usage increment: {str(e)}")

    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Checks the database for an existing record with this idempotency key.
        Prevents duplicate increments during network retries.
        """
        if not key:
            return None

        stmt = select(UsageCounter).where(UsageCounter.idempotency_key == key)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            return {
                "user_id": row.user_id,
                "service": row.service,
                "used": row.used
            }
        return None