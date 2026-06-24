# =========================================================
# FILE: app/api/routes/users.py
# =========================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.repositories.user.user_repository import user_repository
from app.serializers.user_serializer import user_serializer
from app.validators.auth_validator import AuthValidator
from app.validators.user_validator import UserValidator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# =========================================================
# REQUEST MODEL
# =========================================================
class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, min_length=8, max_length=30)


# =========================================================
# HELPERS
# =========================================================
async def _get_user_or_none(db: AsyncSession, auth_uid: str):
    try:
        return await user_repository.get_by_auth_uid(db, auth_uid=auth_uid)
    except Exception:
        logger.exception("Failed to load user auth_uid=%s", auth_uid)
        return None


def _require_self_or_admin(current_user: Any, auth_uid: str) -> None:
    if getattr(current_user, "is_admin", False):
        return

    if str(getattr(current_user, "auth_uid", "")).strip() == str(auth_uid).strip():
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not allowed to access this user",
    )


# =========================================================
# GET ME
# =========================================================
@router.get("/me", response_model=Dict[str, Any])
async def get_me(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    user = await _get_user_or_none(db, getattr(current_user, "auth_uid", ""))

    if user is None:
        return user_serializer.to_response(current_user)

    return user_serializer.to_response(user)


# =========================================================
# UPDATE ME
# =========================================================
@router.patch("/me", response_model=Dict[str, Any])
async def update_me(
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    try:
        user = await _get_user_or_none(db, getattr(current_user, "auth_uid", ""))

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # =====================================================
        # VALIDATION LAYER
        # =====================================================
        if payload.name is not None:
            user.name = UserValidator.validate_full_name(payload.name)

        if payload.email is not None:
            user.email = AuthValidator.validate_email(str(payload.email))

        if payload.phone is not None:
            user.phone = AuthValidator.validate_phone(payload.phone)

        # =====================================================
        # TIMESTAMP (CLEAN FIX - NO __import__)
        # =====================================================
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(user)

        logger.info("[USER_UPDATED] auth_uid=%s", getattr(current_user, "auth_uid", ""))

        return user_serializer.to_response(user)

    except HTTPException:
        raise

    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:
        await db.rollback()
        logger.exception("User update failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        ) from exc


# =========================================================
# GET BY AUTH UID
# =========================================================
@router.get("/{auth_uid}", response_model=Dict[str, Any])
async def get_user_by_auth_uid(
    auth_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _require_self_or_admin(current_user, auth_uid)

    user = await _get_user_or_none(db, auth_uid)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user_serializer.to_response(user)