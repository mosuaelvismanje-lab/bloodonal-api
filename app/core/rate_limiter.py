from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Production-grade rate limiter.

    Supports:
    - topic-based throttling
    - user-based throttling
    - action-based throttling
    - Redis-backed distributed throttling
    - in-memory fallback for local development

    Notes:
    - If you pass an async Redis client (for example redis.asyncio),
      use the async methods below.
    - This implementation is safe for multi-worker deployments when Redis is used.
    """

    def __init__(
        self,
        default_cooldown_seconds: int = 30,
        redis_client: Optional[Any] = None,
    ) -> None:
        self.default_cooldown = max(int(default_cooldown_seconds), 1)
        self.redis = redis_client

        # Fallback for dev / single-process mode only.
        self._memory_store: Dict[str, float] = {}

    # =========================================================
    # KEY BUILDER
    # =========================================================
    def _key(self, scope: str, identifier: str) -> str:
        safe_scope = (scope or "global").strip().lower()
        safe_identifier = (identifier or "unknown").strip().lower()
        return f"rate:{safe_scope}:{safe_identifier}"

    # =========================================================
    # REDIS HELPERS
    # =========================================================
    async def _redis_get(self, key: str) -> Optional[float]:
        if not self.redis:
            return None

        value = await self.redis.get(key)
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def _redis_set(self, key: str, timestamp: float, ttl_seconds: int) -> None:
        if not self.redis:
            return

        # Prefer atomic TTL so stale keys disappear automatically.
        try:
            await self.redis.set(key, str(timestamp), ex=ttl_seconds)
        except TypeError:
            # Fallback if client does not accept ex (rare)
            await self.redis.set(key, str(timestamp))

    async def _redis_delete(self, key: str) -> None:
        if self.redis:
            await self.redis.delete(key)

    # =========================================================
    # CHECK ALLOWANCE
    # =========================================================
    async def allow(
        self,
        scope: str,
        identifier: str,
        cooldown_seconds: Optional[int] = None,
    ) -> bool:
        """
        Returns True if the action is allowed now.
        """

        cooldown = max(int(cooldown_seconds or self.default_cooldown), 1)
        key = self._key(scope, identifier)
        now = time.time()

        # =====================================================
        # REDIS MODE (PRODUCTION)
        # =====================================================
        if self.redis is not None:
            try:
                last_time = await self._redis_get(key)

                if last_time is not None and (now - last_time) < cooldown:
                    return False

                await self._redis_set(key, now, cooldown)
                return True

            except Exception as e:
                logger.error("[RATE_LIMIT_REDIS_ERROR] %s", e)

        # =====================================================
        # MEMORY MODE (DEV / SINGLE PROCESS FALLBACK)
        # =====================================================
        last_time = self._memory_store.get(key)

        if last_time is not None and (now - last_time) < cooldown:
            return False

        self._memory_store[key] = now
        return True

    # =========================================================
    # RESET ONE LIMIT
    # =========================================================
    async def reset(self, scope: str, identifier: str) -> None:
        key = self._key(scope, identifier)

        if self.redis is not None:
            try:
                await self._redis_delete(key)
            except Exception as e:
                logger.error("[RATE_LIMIT_RESET_REDIS_ERROR] %s", e)

        self._memory_store.pop(key, None)

    # =========================================================
    # RESET ALL IN SCOPE
    # =========================================================
    async def reset_scope(self, scope: str) -> None:
        """
        Clears all keys under a scope.
        Useful for admin resets or scheduled cleanup.
        """

        scope_prefix = f"rate:{(scope or 'global').strip().lower()}:"

        if self.redis is not None:
            try:
                async for key in self.redis.scan_iter(match=f"{scope_prefix}*"):
                    await self.redis.delete(key)
            except Exception as e:
                logger.error("[RATE_LIMIT_SCOPE_RESET_REDIS_ERROR] %s", e)

        self._memory_store = {
            k: v for k, v in self._memory_store.items()
            if not k.startswith(scope_prefix)
        }

    # =========================================================
    # PRESET HELPERS
    # =========================================================
    async def allow_topic(self, topic: str, cooldown: int = 30) -> bool:
        return await self.allow("topic", topic, cooldown)

    async def allow_user(self, user_id: str, cooldown: int = 10) -> bool:
        return await self.allow("user", user_id, cooldown)

    async def allow_action(self, action: str, identifier: str, cooldown: int = 5) -> bool:
        return await self.allow(f"action:{action}", identifier, cooldown)