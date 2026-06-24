from __future__ import annotations

from typing import Optional

from app.core.rate_limiter import RateLimiter
from app.modules.notification.notification_service import NotificationService


class Container:
    """
    Central Dependency Injection Container (Production Grade)

    Responsibilities:
    -------------------------------------------------
    - Hold shared infrastructure (Redis, etc.)
    - Lazily initialize services
    - Ensure single instance per service
    - Keep services decoupled and testable
    """

    def __init__(self, redis_client: Optional[object] = None):
        self.redis_client = redis_client

        # Lazy-loaded services (initialized only when needed)
        self._rate_limiter: Optional[RateLimiter] = None
        self._notification_service: Optional[NotificationService] = None

    # =========================================================
    # RATE LIMITER
    # =========================================================
    @property
    def rate_limiter(self) -> RateLimiter:
        """
        Lazy init RateLimiter (Redis-backed)
        """
        if self._rate_limiter is None:
            self._rate_limiter = RateLimiter(
                redis_client=self.redis_client
            )
        return self._rate_limiter

    # =========================================================
    # NOTIFICATION SERVICE
    # =========================================================
    @property
    def notification_service(self) -> NotificationService:
        """
        Lazy init NotificationService
        Injects Redis + RateLimiter
        """
        if self._notification_service is None:
            self._notification_service = NotificationService(
                repo=None,
                redis_client=self.redis_client,
                rate_limiter=self.rate_limiter,  # 🔥 inject shared limiter
            )
        return self._notification_service

    # =========================================================
    # FUTURE SERVICES (PLUG & PLAY)
    # =========================================================
    # Example:
    #
    # @property
    # def reward_service(self) -> RewardService:
    #     if not hasattr(self, "_reward_service"):
    #         self._reward_service = RewardService(...)
    #     return self._reward_service