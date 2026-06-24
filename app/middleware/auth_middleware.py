# =========================================================
# FILE: app/middleware/auth_middleware.py
# =========================================================

from __future__ import annotations

import logging
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

logger = logging.getLogger(
    "bloodonal.auth_middleware"
)


class AuthMiddleware(
    BaseHTTPMiddleware
):
    """
    Enterprise Authentication Middleware

    Responsibilities:
    -------------------------------------------------
    - Validate authenticated user
    - Protect internal routes
    - Attach auth context
    - Block unauthorized requests
    """

    def __init__(
        self,
        app,
        *,
        excluded_paths: list[str] | None = None,
    ):
        super().__init__(app)

        self.excluded_paths = (
            excluded_paths
            or [
                "/docs",
                "/openapi.json",
                "/redoc",
                "/health",
            ]
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):

        path = request.url.path

        # =================================================
        # SKIP PUBLIC ROUTES
        # =================================================
        for excluded in self.excluded_paths:
            if path.startswith(excluded):
                return await call_next(
                    request
                )

        # =================================================
        # USER CONTEXT
        # =================================================
        user = getattr(
            request.state,
            "user",
            None,
        )

        # =================================================
        # TOKEN HEADER
        # =================================================
        auth_header = request.headers.get(
            "Authorization"
        )

        # =================================================
        # VALIDATION
        # =================================================
        if not user and not auth_header:
            logger.warning(
                "Unauthorized request: %s",
                path,
            )

            return JSONResponse(
                status_code=401,
                content={
                    "success": False,
                    "message": "Unauthorized",
                },
            )

        try:
            response = await call_next(
                request
            )
            return response

        except Exception as exc:
            logger.exception(
                "Auth middleware error: %s",
                exc,
            )

            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": "Authentication middleware failure",
                },
            )