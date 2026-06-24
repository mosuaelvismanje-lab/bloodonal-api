from __future__ import annotations

import time
import uuid
import logging
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


# =========================================================
# REQUEST TRACKING MIDDLEWARE (PRODUCTION READY)
# =========================================================
class RequestTrackingMiddleware(BaseHTTPMiddleware):
    """
    Enterprise-grade middleware for:

    - Request correlation ID
    - Latency tracking
    - Structured logging
    - Safe observability hooks

    RULES:
    - No business logic
    - No DB access
    - No domain imports
    """

    def __init__(
        self,
        app,
        enable_response_headers: bool = True,
        enable_logging: bool = True,
    ):
        super().__init__(app)
        self.enable_response_headers = enable_response_headers
        self.enable_logging = enable_logging

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        start_time = time.perf_counter()

        request.state.request_id = request_id

        try:
            response: Response = await call_next(request)

            process_time = time.perf_counter() - start_time

            if self.enable_response_headers:
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = f"{process_time:.6f}"

            if self.enable_logging:
                logger.info(
                    "http_request",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "process_time_ms": round(process_time * 1000, 2),
                    },
                )

            return response

        except Exception as exc:
            process_time = time.perf_counter() - start_time

            logger.exception(
                "http_request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "process_time_ms": round(process_time * 1000, 2),
                    "error": str(exc),
                },
            )
            raise


# =========================================================
# RESPONSE ENVELOPE MIDDLEWARE (OPTIONAL ONLY)
# =========================================================
class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """
    OPTIONAL ONLY (disabled by default)

    WARNING:
    - Do NOT enable globally if you have:
      - file downloads
      - streaming endpoints
      - websocket APIs

    Prefer explicit:
    success()/error() response pattern instead.
    """

    def __init__(self, app, enabled: bool = False):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        if not self.enabled:
            return response

        content_type = response.headers.get("content-type", "")

        # Only wrap JSON APIs
        if "application/json" not in content_type:
            return response

        return response