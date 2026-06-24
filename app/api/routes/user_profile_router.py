# =========================================================
# FILE: app/api/routes/user_profile_routes.py
# =========================================================

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.mapper.profile_mapper import profile_mapper
from app.repositories.user.user_repository import user_repository
from app.services.user.profile_service import profile_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users/profile",
    tags=["User Profile"],
)

# =========================================================
# REQUEST MODELS (KEEP LIGHTWEIGHT IN ROUTER)
# =========================================================
class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=30)
    email: EmailStr | None = None
    bio: str | None = Field(default=None, max_length=500)
    gender: str | None = Field(default=None, max_length=30)
    avatar_url: str | None = Field(default=None, max_length=1000)

    # 🩸 BLOOD SYSTEM
    blood_group: str | None = Field(default=None, max_length=5)


class AvatarUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    avatar_url: str = Field(..., min_length=5, max_length=1000)


# =========================================================
# HELPERS
# =========================================================
async def _get_user(db: AsyncSession, auth_uid: str):
    return await user_repository.get_by_auth_uid(db, auth_uid=auth_uid)


def _require_self_or_admin(current_user: Any, auth_uid: str) -> None:
    if getattr(current_user, "is_admin", False):
        return

    if str(getattr(current_user, "auth_uid", "")).strip() == auth_uid.strip():
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not allowed to access this profile",
    )


# =========================================================
# GET CURRENT PROFILE
# =========================================================
@router.get("/me", response_model=Dict[str, Any])
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    user = await _get_user(db, current_user.auth_uid)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    profile = getattr(user, "profile", None)

    return {
        "success": True,
        "profile": profile_mapper.to_response(profile),
    }


# =========================================================
# UPDATE PROFILE (ALL LOGIC IN SERVICE)
# =========================================================
@router.patch("/me", response_model=Dict[str, Any])
async def update_my_profile(
    payload: ProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    try:
        result = await profile_service.update_profile(
            db,
            auth_uid=current_user.auth_uid,
            full_name=payload.full_name,
            username=payload.username,
            email=str(payload.email) if payload.email else None,
            bio=payload.bio,
            gender=payload.gender,
            avatar_url=payload.avatar_url,
            blood_group=payload.blood_group,
        )

        return {
            "success": True,
            "profile": result,
        }

    except Exception as exc:
        logger.exception("Profile update failed")
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


# =========================================================
# UPDATE AVATAR
# =========================================================
@router.put("/me/avatar", response_model=Dict[str, Any])
async def update_avatar(
    payload: AvatarUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    try:
        return await profile_service.update_avatar(
            db,
            auth_uid=current_user.auth_uid,
            avatar_url=payload.avatar_url,
        )

    except Exception as exc:
        logger.exception("Avatar update failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to update avatar",
        ) from exc


# =========================================================
# DELETE AVATAR
# =========================================================
@router.delete("/me/avatar", response_model=Dict[str, Any])
async def delete_avatar(
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    try:
        return await profile_service.delete_avatar(
            db,
            auth_uid=current_user.auth_uid,
        )

    except Exception as exc:
        logger.exception("Avatar delete failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete avatar",
        ) from exc


# =========================================================
# GET PROFILE BY AUTH UID
# =========================================================
@router.get("/{auth_uid}", response_model=Dict[str, Any])
async def get_profile_by_auth_uid(
    auth_uid: str,
    db: AsyncSession = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    _require_self_or_admin(current_user, auth_uid)

    user = await _get_user(db, auth_uid)

    if not user:
        raise HTTPException(404, "Profile not found")

    profile = getattr(user, "profile", None)

    return {
        "success": True,
        "profile": profile_mapper.to_response(profile),
    }