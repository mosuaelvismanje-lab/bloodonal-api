from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_admin_user, get_db_session
from app.core.api.response import success, error

from app.admin.operations.service import (
    AdminOperationsService,
    AdminOperationsError,
    AdminOperationConflictError,
    AdminOperationNotFoundError,
    AdminOperationValidationError,
)

from app.schemas.payment_admin import (
    AdminConfirmPaymentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/operations",
    tags=["Admin Operations"],
)


# =========================================================
# ADMIN GUARD
# =========================================================
def require_admin(user=Depends(get_admin_user)):
    if not getattr(user, "is_admin", False):
        logger.warning(
            "unauthorized_admin_access",
            extra={"user_id": getattr(user, "id", None)},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# =========================================================
# SERVICE FACTORY
# =========================================================
def get_service(
    db: AsyncSession = Depends(get_db_session),
) -> AdminOperationsService:
    return AdminOperationsService(db=db)


# =========================================================
# ERROR MAPPER
# =========================================================
def _map_error(exc: Exception) -> JSONResponse:
    if isinstance(exc, AdminOperationValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error(
                message=str(exc),
                error_code="ADMIN_OPERATION_VALIDATION_ERROR",
            ),
        )

    if isinstance(exc, AdminOperationNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error(
                message=str(exc),
                error_code="ADMIN_OPERATION_NOT_FOUND",
            ),
        )

    if isinstance(exc, AdminOperationConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error(
                message=str(exc),
                error_code="ADMIN_OPERATION_CONFLICT",
            ),
        )

    if isinstance(exc, AdminOperationsError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error(
                message=str(exc),
                error_code="ADMIN_OPERATION_ERROR",
            ),
        )

    logger.exception("admin_operations_unhandled_exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error(
            message="Internal server error",
            error_code="INTERNAL_SERVER_ERROR",
        ),
    )


# =========================================================
# VERIFY PAYMENT OVERRIDE
# =========================================================
@router.post("/verify-bypass", response_model=Dict[str, Any])
async def verify_payment_override(
    req: AdminConfirmPaymentRequest,
    admin=Depends(require_admin),
    service: AdminOperationsService = Depends(get_service),
):
    try:
        result = await service.verify_payment_override(
            request=req,
            admin_email=getattr(admin, "email", "unknown"),
        )

        return success(
            data=result,
            message="Payment verified and service activated",
        )

    except Exception as exc:
        return _map_error(exc)


# =========================================================
# RECENT PAYMENTS
# =========================================================
@router.get("/recent-payments", response_model=Dict[str, Any])
async def get_recent_payments(
    limit: int = 50,
    admin=Depends(require_admin),
    service: AdminOperationsService = Depends(get_service),
):
    try:
        items = await service.get_recent_payments(limit=limit)

        return success(
            data=items,
            message="Recent payments loaded",
        )

    except Exception as exc:
        return _map_error(exc)


# =========================================================
# HEALTH
# =========================================================
@router.get("/health", response_model=Dict[str, Any])
async def health(admin=Depends(require_admin)):
    return success(
        data={
            "module": "admin_operations",
            "status": "ok",
        },
        message="Admin operations healthy",
    )