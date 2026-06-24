# =========================================================
# FILE: app/schemas/user/user_response.py
# =========================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, EmailStr

from app.schemas.base import BaseSchema


class UserResponse(BaseSchema):
    """
    =========================================================
    ENTERPRISE USER RESPONSE DTO
    =========================================================
    Safe for:
    - mobile app
    - admin dashboard
    - realtime sync
    - notifications
    - profile rendering
    =========================================================
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    # =====================================================
    # IDENTIFIERS
    # =====================================================
    uid: UUID
    auth_uid: str

    # =====================================================
    # BASIC INFO
    # =====================================================
    email: EmailStr
    name: str

    # =====================================================
    # ROLE / ACCESS
    # =====================================================
    role: str
    is_admin: bool

    # =====================================================
    # ACCOUNT STATUS
    # =====================================================
    is_active: bool
    is_verified: bool

    # =====================================================
    # DEVICE / APP
    # =====================================================
    platform: Optional[str] = None
    device_id: Optional[str] = None
    device_model: Optional[str] = None
    app_version: Optional[str] = None

    # =====================================================
    # LOGIN TRACKING
    # =====================================================
    login_count: int = 0

    last_login_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None

    # =====================================================
    # NOTIFICATIONS
    # =====================================================
    fcm_token: Optional[str] = None

    # =====================================================
    # AUDIT
    # =====================================================
    created_at: datetime
    updated_at: Optional[datetime] = None