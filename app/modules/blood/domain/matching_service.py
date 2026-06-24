from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.modules.blood.domain.adapter import BloodMatchingAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MatchingConfig:
    DEFAULT_LIMIT: int = 20
    MAX_LIMIT: int = 100


class MatchingService:
    """
    Enterprise matching orchestration layer.

    Responsibilities:
    - delegate matching to the adapter only
    - keep orchestration thin and deterministic
    - avoid duplicating validation, rules, scoring, or enrichment
    - support both sync and async adapters safely
    """

    def __init__(
        self,
        adapter: Optional[BloodMatchingAdapter] = None,
        config: Optional[MatchingConfig] = None,
    ) -> None:
        self.adapter = adapter or BloodMatchingAdapter()
        self.config = config or MatchingConfig()

    # =========================================================
    # MAIN ENTRY
    # =========================================================
    async def get_matches(
        self,
        db: Any,
        blood_request: Any,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        if blood_request is None:
            logger.warning("matching_service_null_request")
            return []

        normalized_limit = self._normalize_limit(limit)

        try:
            result = self.adapter.get_matches(
                db=db,
                blood_request=blood_request,
                limit=normalized_limit,
            )

            if inspect.isawaitable(result):
                result = await result

            if result is None:
                return []

            if not isinstance(result, list):
                logger.error(
                    "matching_service_invalid_adapter_response",
                    extra={
                        "response_type": type(result).__name__,
                    },
                )
                return []

            return result

        except Exception:
            logger.exception("matching_service_adapter_failure")
            return []

    # =========================================================
    # INTERNALS
    # =========================================================
    def _normalize_limit(self, limit: int) -> int:
        if not isinstance(limit, int):
            raise TypeError("limit must be an integer")

        if limit <= 0:
            return self.config.DEFAULT_LIMIT

        if limit > self.config.MAX_LIMIT:
            return self.config.MAX_LIMIT

        return limit