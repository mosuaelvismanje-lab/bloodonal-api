# =========================================================
# FILE: app/routes/auth_routes.py
# =========================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import MockUser, get_current_user, get_db

# =========================================================
# TOKEN UTILS (NEW INTEGRATION)
# =========================================================
from app.utils.token_utils import (
    generate_token,
    generate_numeric_otp,
    generate_correlation_id,
    stable_uuid,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

# =========================================================
# OPTIONAL MODEL IMPORT
# =========================================================
try:
    from app.models.user import User  # type: ignore
except Exception:
    User = None  # type: ignore


# =========================================================
# REQUEST MODELS
# =========================================================
class FcmTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fcm_token: str = Field(..., min_length=1, max_length=512)


# =========================================================
# RESPONSE MODELS
# =========================================================
class UserResponse(BaseModel):
    uid: str
    email: str
    name: str
    role: str
    is_admin: bool


class SyncResponse(BaseModel):
    success: bool
    message: str
    user: UserResponse
    created: bool
    updated_at: datetime
    correlation_id: str  # NEW


class FcmTokenResponse(BaseModel):
    success: bool
    message: str
    correlation_id: str  # NEW


class ValidationResponse(BaseModel):
    valid: bool
    uid: str
    stable_id: str  # NEW (stable UUID)


class LogoutResponse(BaseModel):
    success: bool
    message: str
    correlation_id: str  # NEW


# =========================================================
# HELPERS
# =========================================================
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _build_user_response(current_user: MockUser) -> UserResponse:
    return UserResponse(
        uid=str(current_user.uid),
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        is_admin=current_user.is_admin,
    )


# =========================================================
# USER SYNC (DB)
# =========================================================
async def _find_user(db: AsyncSession, current_user: MockUser):
    if User is None:
        return None

    query = select(User)

    conditions = []
    if hasattr(User, "auth_uid"):
        conditions.append(User.auth_uid == str(current_user.auth_uid))
    if hasattr(User, "email"):
        conditions.append(User.email == current_user.email.lower().strip())

    if not conditions:
        return None

    from sqlalchemy import or_

    query = query.where(or_(*conditions))

    if hasattr(User, "deleted_at"):
        query = query.where(User.deleted_at.is_(None))

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _sync_user(
    db: AsyncSession,
    current_user: MockUser,
    *,
    platform: Optional[str] = None,
    device_id: Optional[str] = None,
    device_model: Optional[str] = None,
    app_version: Optional[str] = None,
) -> tuple[bool, datetime]:

    if User is None:
        return False, _now_utc()

    try:
        user = await _find_user(db, current_user)
        created = user is None

        if user is None:
            user = User()  # type: ignore
            db.add(user)

            if hasattr(user, "created_at"):
                user.created_at = _now_utc()

        # =================================================
        # CORE FIELDS
        # =================================================
        if hasattr(user, "auth_uid"):
            user.auth_uid = str(current_user.auth_uid)

        if hasattr(user, "email"):
            user.email = current_user.email.lower().strip()

        if hasattr(user, "name"):
            user.name = current_user.name

        if hasattr(user, "role"):
            user.role = current_user.role

        if hasattr(user, "is_admin"):
            user.is_admin = current_user.is_admin

        if hasattr(user, "is_active"):
            user.is_active = True

        # =================================================
        # DEVICE INFO
        # =================================================
        if hasattr(user, "platform") and platform:
            user.platform = platform

        if hasattr(user, "device_id") and device_id:
            user.device_id = device_id

        if hasattr(user, "device_model") and device_model:
            user.device_model = device_model

        if hasattr(user, "app_version") and app_version:
            user.app_version = app_version

        # =================================================
        # TOKEN UTILS USAGE (CORRELATION / STABLE ID)
        # =================================================
        if hasattr(user, "correlation_id"):
            user.correlation_id = generate_correlation_id()

        if hasattr(user, "stable_uid"):
            user.stable_uid = str(
                stable_uuid(str(current_user.auth_uid))
            )

        # =================================================
        # TIMESTAMPS
        # =================================================
        if hasattr(user, "last_login_at"):
            user.last_login_at = _now_utc()

        if hasattr(user, "updated_at"):
            user.updated_at = _now_utc()

        await db.commit()
        await db.refresh(user)

        return created, getattr(user, "updated_at", _now_utc())

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("User sync failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User sync failed",
        ) from exc


# =========================================================
# FCM TOKEN UPDATE
# =========================================================
async def _update_fcm(
    db: AsyncSession,
    current_user: MockUser,
    token: str,
    correlation_id: str,
):
    if User is None:
        return

    try:
        query = select(User)

        if hasattr(User, "auth_uid"):
            query = query.where(User.auth_uid == str(current_user.auth_uid))
        elif hasattr(User, "email"):
            query = query.where(User.email == current_user.email.lower().strip())

        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return

        if hasattr(user, "fcm_token"):
            user.fcm_token = token

        if hasattr(user, "updated_at"):
            user.updated_at = _now_utc()

        if hasattr(user, "correlation_id"):
            user.correlation_id = correlation_id

        await db.commit()
        await db.refresh(user)

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("FCM update failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="FCM update failed",
        ) from exc


# =========================================================
# ROUTES
# =========================================================

@router.post("/sync", response_model=SyncResponse)
async def sync_user(
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_app_platform: Optional[str] = Header(default=None),
    x_device_id: Optional[str] = Header(default=None),
    x_device_model: Optional[str] = Header(default=None),
    x_app_version: Optional[str] = Header(default=None),
):

    correlation_id = generate_correlation_id()

    created, updated_at = await _sync_user(
        db,
        current_user,
        platform=_normalize_optional(x_app_platform),
        device_id=_normalize_optional(x_device_id),
        device_model=_normalize_optional(x_device_model),
        app_version=_normalize_optional(x_app_version),
    )

    return SyncResponse(
        success=True,
        message="User synchronized successfully",
        user=_build_user_response(current_user),
        created=created,
        updated_at=updated_at,
        correlation_id=correlation_id,
    )


@router.put("/fcm-token", response_model=FcmTokenResponse)
async def update_fcm_token(
    request: FcmTokenRequest,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    token = request.fcm_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="FCM token required",
        )

    correlation_id = generate_correlation_id()

    await _update_fcm(db, current_user, token, correlation_id)

    return FcmTokenResponse(
        success=True,
        message="FCM token updated",
        correlation_id=correlation_id,
    )


@router.get("/validate", response_model=ValidationResponse)
async def validate_token(
    current_user: MockUser = Depends(get_current_user),
):

    stable_id = str(
        stable_uuid(str(current_user.auth_uid))
    )

    if hasattr(current_user, "is_active") and not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    return ValidationResponse(
        valid=True,
        uid=str(current_user.uid),
        stable_id=stable_id,
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    current_user: MockUser = Depends(get_current_user),
):

    correlation_id = generate_correlation_id()

    logger.info(
        "[LOGOUT] user=%s correlation_id=%s",
        current_user.uid,
        correlation_id,
    )

    return LogoutResponse(
        success=True,
        message="Logout successful",
        correlation_id=correlation_id,
    )