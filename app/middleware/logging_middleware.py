# =========================================================
# FILE: app/middleware/logging_middleware.py
# =========================================================

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

logger = logging.getLogger(
    "bloodonal.request_logger"
)


class LoggingMiddleware(
    BaseHTTPMiddleware
):
    """
    Enterprise Request Logging Middleware

    Responsibilities:
    -------------------------------------------------
    - Request correlation IDs
    - Structured request logging
    - Response timing
    - Exception visibility
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):

        request_id = str(uuid.uuid4())

        request.state.request_id = (
            request_id
        )

        start_time = time.perf_counter()

        logger.info(
            "[REQUEST_START] %s %s | request_id=%s",
            request.method,
            request.url.path,
            request_id,
        )

        try:
            response = await call_next(
                request
            )

            process_time = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000,
                2,
            )

            response.headers[
                "X-Request-ID"
            ] = request_id

            response.headers[
                "X-Process-Time-MS"
            ] = str(process_time)

            logger.info(
                "[REQUEST_END] %s %s | status=%s | duration_ms=%s | request_id=%s",
                request.method,
                request.url.path,
                response.status_code,
                process_time,
                request_id,
            )

            return response

        except Exception as exc:
            process_time = round(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000,
                2,
            )

            logger.exception(
                "[REQUEST_FAIL] %s %s | duration_ms=%s | request_id=%s | error=%s",
                request.method,
                request.url.path,
                process_time,
                request_id,
                exc,
            )

            raise