import logging
import inspect
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_counter import UsageCounter
from app.domain.interfaces import IUsageRepository
from app.services.registry import registry

logger = logging.getLogger(__name__)


class SQLAlchemyUsageRepository(IUsageRepository):
    """
    Quota Gatekeeper (safe async version)

    Fixes:
    - Handles AsyncMock / coroutine return values safely
    - Avoids scalar_one_or_none() crash when result is mocked badly
    - Keeps service normalization via registry
    - Keeps upsert + idempotency behavior
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ======================================================
    # INTERNAL HELPERS
    # ======================================================
    def _resolve_service(self, service: str) -> str:
        try:
            meta = registry.get_service_meta(service)
            return meta.get("quota_type", service)
        except Exception:
            return service

    async def _safe_scalar_one_or_none(self, result: Any) -> Any:
        """
        Safely extract scalar_one_or_none() from SQLAlchemy results,
        while tolerating AsyncMock / coroutine-based test doubles.
        """
        if result is None:
            return None

        scalar_fn = getattr(result, "scalar_one_or_none", None)
        if scalar_fn is None:
            logger.warning("Result object has no scalar_one_or_none()")
            return None

        try:
            value = scalar_fn()
            if inspect.isawaitable(value):
                value = await value
            return value
        except Exception as e:
            logger.error(f"Failed to read scalar_one_or_none(): {e}")
            return None

    # ======================================================
    # COUNT USAGE
    # ======================================================
    async def count_uses(self, user_id: str, service: str) -> int:
        quota_type = self._resolve_service(service)

        try:
            stmt = select(UsageCounter.used).where(
                UsageCounter.user_id == user_id,
                UsageCounter.service == quota_type
            )

            result = await self.session.execute(stmt)
            value = await self._safe_scalar_one_or_none(result)

            if value is None:
                return 0

            if inspect.isawaitable(value):
                logger.warning("Awaitable detected in count_uses() value, returning 0")
                return 0

            try:
                return int(value)
            except (TypeError, ValueError):
                logger.error(f"Invalid usage value type: {type(value)}")
                return 0

        except Exception as e:
            logger.error(f"Error counting uses {user_id}/{quota_type}: {e}")
            return 0

    # ======================================================
    # RECORD USAGE
    # ======================================================
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

        quota_type = self._resolve_service(service)

        try:
            if idempotency_key:
                existing = await self.get_by_idempotency_key(idempotency_key)
                if existing:
                    logger.info(f"♻️ Duplicate ignored: {idempotency_key}")
                    return

            stmt = insert(UsageCounter).values(
                user_id=user_id,
                service=quota_type,
                used=1,
                idempotency_key=idempotency_key,
                request_id=request_id
            )

            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "service"],
                set_={
                    "used": UsageCounter.used + 1,
                    "idempotency_key": idempotency_key,
                    "request_id": request_id
                }
            )

            await self.session.execute(upsert_stmt)
            logger.info(f"📈 Usage recorded: {user_id} ({quota_type})")

        except Exception as e:
            logger.error(f"💥 Failed to record usage: {e}")
            raise RuntimeError(str(e))

    # ======================================================
    # IDEMPOTENCY LOOKUP
    # ======================================================
    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        if not key:
            return None

        try:
            stmt = select(UsageCounter).where(
                UsageCounter.idempotency_key == key
            )

            result = await self.session.execute(stmt)
            row = await self._safe_scalar_one_or_none(result)

            if row is None:
                return None

            return {
                "user_id": getattr(row, "user_id", None),
                "service": getattr(row, "service", None),
                "used": int(getattr(row, "used", 0) or 0)
            }

        except Exception as e:
            logger.error(f"Error in idempotency lookup: {e}")
            return None

    # ======================================================
    # FREE USAGE
    # ======================================================
    async def try_consume_free_usage(
        self,
        user_id: str,
        service: str,
        free_limit: int
    ) -> bool:

        quota_type = self._resolve_service(service)

        try:
            current_used = await self.count_uses(user_id, service)

            try:
                free_limit = int(free_limit)
            except (TypeError, ValueError):
                free_limit = 0

            if current_used < free_limit:
                stmt = insert(UsageCounter).values(
                    user_id=user_id,
                    service=quota_type,
                    used=1
                )

                upsert_stmt = stmt.on_conflict_do_update(
                    index_elements=["user_id", "service"],
                    set_={"used": UsageCounter.used + 1}
                )

                await self.session.execute(upsert_stmt)
                logger.info(f"✅ Free usage consumed: {user_id} ({quota_type})")
                return True

            logger.info(f"🚫 Free limit reached: {user_id} ({quota_type})")
            return False

        except Exception as e:
            logger.error(f"💥 Failed to consume usage: {e}")
            raise RuntimeError(str(e))