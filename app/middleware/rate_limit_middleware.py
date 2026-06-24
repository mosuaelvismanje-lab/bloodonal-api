# =========================================================
# FILE: app/middleware/rate_limit_middleware.py
# =========================================================

from __future__ import annotations

import logging
import time
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

logger = logging.getLogger(
    "bloodonal.rate_limit"
)


class InMemoryRateLimiter:
    """
    Simple enterprise-safe fallback limiter.

    Replace with Redis implementation
    in production cluster deployment.
    """

    def __init__(
        self,
        requests: int = 100,
        window_seconds: int = 60,
    ):
        self.requests = requests
        self.window_seconds = (
            window_seconds
        )
        self.storage: dict[
            str,
            list[float]
        ] = {}

    def allow(
        self,
        key: str,
    ) -> bool:

        current = time.time()

        if key not in self.storage:
            self.storage[key] = []

        # =============================================
        # CLEAN EXPIRED
        # =============================================
        self.storage[key] = [
            ts
            for ts in self.storage[key]
            if (
                current - ts
            )
            < self.window_seconds
        ]

        # =============================================
        # BLOCK
        # =============================================
        if (
            len(self.storage[key])
            >= self.requests
        ):
            return False

        self.storage[key].append(
            current
        )

        return True


class RateLimitMiddleware(
    BaseHTTPMiddleware
):
    """
    Enterprise Rate Limit Middleware

    Responsibilities:
    -------------------------------------------------
    - Prevent abuse
    - Prevent spam traffic
    - Protect APIs
    - Add response metadata
    """

    def __init__(
        self,
        app,
        *,
        limiter: (
            InMemoryRateLimiter | None
        ) = None,
    ):
        super().__init__(app)

        self.limiter = (
            limiter
            or InMemoryRateLimiter()
        )

    def _client_ip(
        self,
        request: Request,
    ) -> str:

        forwarded = request.headers.get(
            "X-Forwarded-For"
        )

        if forwarded:
            return (
                forwarded.split(",")[0]
                .strip()
            )

        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):

        ip = self._client_ip(
            request
        )

        path = request.url.path

        key = f"{ip}:{path}"

        allowed = self.limiter.allow(
            key
        )

        if not allowed:
            logger.warning(
                "Rate limit exceeded: %s",
                key,
            )

            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "message": "Too many requests",
                },
                headers={
                    "Retry-After": "60",
                },
            )

        response = await call_next(
            request
        )

        response.headers[
            "X-RateLimit-Limit"
        ] = str(
            self.limiter.requests
        )

        response.headers[
            "X-RateLimit-Window"
        ] = str(
            self.limiter.window_seconds
        )

        return response