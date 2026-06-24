# =========================================================
# FILE: app/schemas/user/profile_response.py
# =========================================================

from __future__ import annotations

from datetime import datetime, date
from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, EmailStr, computed_field

from app.schemas.user.base import BaseSchema


class ProfileResponse(BaseSchema):
    """
    =========================================================
    FULL USER PROFILE RESPONSE (ENTERPRISE + HEALTHCARE)
    =========================================================
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    # =====================================================
    # CORE USER
    # =====================================================
    uid: UUID
    auth_uid: str

    email: EmailStr
    name: str

    role: str

    is_admin: bool
    is_active: bool
    is_verified: bool

    # =====================================================
    # PROFILE BASIC
    # =====================================================
    username: Optional[str] = None
    bio: Optional[str] = None
    gender: Optional[str] = None

    avatar_url: Optional[str] = None
    cover_photo_url: Optional[str] = None

    phone_number: Optional[str] = None

    # =====================================================
    # LOCATION
    # =====================================================
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    # =====================================================
    # PERSONAL
    # =====================================================
    birth_date: Optional[date] = None

    # =====================================================
    # BLOOD SYSTEM (NEW - CRITICAL)
    # =====================================================
    blood_group: Optional[str] = None
    is_donor: bool = False
    donation_count: int = 0
    last_donation_at: Optional[datetime] = None

    # =====================================================
    # EMERGENCY CONTACT (NEW)
    # =====================================================
    emergency_contact: Optional[str] = None
    emergency_name: Optional[str] = None
    emergency_relationship: Optional[str] = None

    # =====================================================
    # SOCIAL / REPUTATION
    # =====================================================
    rating: Optional[float] = None
    total_reviews: int = 0
    total_reports: int = 0

    # =====================================================
    # SECURITY
    # =====================================================
    mfa_enabled: bool = False
    suspicious_activity_count: int = 0

    # =====================================================
    # DEVICE / SESSION
    # =====================================================
    platform: Optional[str] = None
    last_seen_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    # =====================================================
    # AUDIT
    # =====================================================
    created_at: datetime
    updated_at: Optional[datetime] = None

    # =====================================================
    # COMPUTED FIELDS
    # =====================================================
    @computed_field
    @property
    def is_online(self) -> bool:
        if not self.last_seen_at:
            return False

        now = datetime.utcnow()
        delta = now - self.last_seen_at.replace(tzinfo=None)

        return delta.total_seconds() <= 300

    @computed_field
    @property
    def display_name(self) -> str:
        return self.username or self.name