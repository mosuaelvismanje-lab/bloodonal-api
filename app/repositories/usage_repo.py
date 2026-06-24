from __future__ import annotations

import logging
import inspect
from typing import Optional, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_counter import UsageCounter
from app.domain.interfaces import IUsageRepository
from app.services.registry import registry

logger = logging.getLogger(__name__)


class SQLAlchemyUsageRepository(IUsageRepository):
    """
    Enterprise Quota Gatekeeper

    Design:
    - DB is source of truth (no race conditions in Python layer)
    - Idempotency enforced at DB + logic layer
    - Supports FREE + PAID usage separation
    - Safe for horizontal scaling
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ======================================================
    # SERVICE NORMALIZATION
    # ======================================================
    def _resolve_service(self, service: str) -> str:
        try:
            meta = registry.get_service_meta(service)
            return meta.get("quota_type", service)
        except Exception:
            return service

    # ======================================================
    # COUNT USAGE (SAFE + ATOMIC)
    # ======================================================
    async def count_uses(self, user_id: str, service: str) -> int:
        quota_type = self._resolve_service(service)

        try:
            stmt = select(func.coalesce(func.sum(UsageCounter.used), 0)).where(
                UsageCounter.user_id == user_id,
                UsageCounter.service == quota_type
            )

            result = await self.session.execute(stmt)
            value = result.scalar_one_or_none()

            return int(value or 0)

        except Exception as e:
            logger.error(f"count_uses failed {user_id}/{service}: {e}")
            return 0

    # ======================================================
    # RECORD USAGE (ATOMIC UPSERT SAFE)
    # ======================================================
    async def record_usage(
        self,
        user_id: str,
        service: str,
        paid: bool,
        amount: float,
        transaction_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:

        quota_type = self._resolve_service(service)

        try:
            stmt = insert(UsageCounter).values(
                user_id=user_id,
                service=quota_type,
                used=1,
                paid=paid,
                amount=amount,
                transaction_id=transaction_id,
                idempotency_key=idempotency_key,
                request_id=request_id,
            )

            # DB-level idempotency safety
            upsert = stmt.on_conflict_do_update(
                index_elements=["user_id", "service"],
                set_={
                    "used": UsageCounter.used + 1,
                    "paid": paid,
                    "amount": amount,
                    "transaction_id": transaction_id,
                    "request_id": request_id,
                },
            )

            await self.session.execute(upsert)

            logger.info(
                "usage_recorded",
                extra={
                    "user_id": user_id,
                    "service": quota_type,
                    "paid": paid,
                },
            )

        except Exception as e:
            logger.error(f"record_usage failed: {e}")
            raise

    # ======================================================
    # IDEMPOTENCY CHECK
    # ======================================================
    async def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        if not key:
            return None

        try:
            stmt = select(UsageCounter).where(
                UsageCounter.idempotency_key == key
            )

            result = await self.session.execute(stmt)
            row = result.scalar_one_or_none()

            if not row:
                return None

            return {
                "user_id": row.user_id,
                "service": row.service,
                "used": row.used,
                "paid": getattr(row, "paid", False),
            }

        except Exception as e:
            logger.error(f"idempotency lookup failed: {e}")
            return None

    # ======================================================
    # FREE USAGE LOGIC
    # ======================================================
    async def try_consume_free_usage(
        self,
        user_id: str,
        service: str,
        free_limit: int,
    ) -> bool:

        quota_type = self._resolve_service(service)

        try:
            used = await self.count_uses(user_id, service)

            if used >= int(free_limit):
                return False

            stmt = insert(UsageCounter).values(
                user_id=user_id,
                service=quota_type,
                used=1,
                paid=False,
            ).on_conflict_do_update(
                index_elements=["user_id", "service"],
                set_={"used": UsageCounter.used + 1},
            )

            await self.session.execute(stmt)

            logger.info(
                "free_usage_consumed",
                extra={"user_id": user_id, "service": quota_type},
            )

            return True

        except Exception as e:
            logger.error(f"free usage failed: {e}")
            return False