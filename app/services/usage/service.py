from __future__ import annotations

import logging
from typing import Optional

from app.repositories.usage_repo import SQLAlchemyUsageRepository

logger = logging.getLogger(__name__)


class UsageService:
    """
    Business rules for usage limits.

    NOT DB logic.
    JUST decisions.
    """

    def __init__(self, usage_repo: SQLAlchemyUsageRepository):
        self.repo = usage_repo

    # ======================================================
    # CAN USER ACCESS SERVICE?
    # ======================================================
    async def can_use_service(
        self,
        user_id: str,
        service: str,
        free_limit: int,
    ) -> bool:

        used = await self.repo.count_uses(user_id, service)

        return used < free_limit

    # ======================================================
    # CONSUME USAGE (SAFE WRAPPER)
    # ======================================================
    async def consume(
        self,
        user_id: str,
        service: str,
        free_limit: int,
        paid: bool = False,
    ) -> bool:

        if not paid:
            can_use = await self.can_use_service(
                user_id, service, free_limit
            )

            if not can_use:
                return False

        await self.repo.try_consume_free_usage(
            user_id=user_id,
            service=service,
            free_limit=free_limit,
        )

        return True