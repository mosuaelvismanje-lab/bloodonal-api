# =========================================================
# FILE: app/schemas/user/profile_update_request.py
# =========================================================

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import (
    ConfigDict,
    Field,
    field_validator,
)

from app.modules.blood.domain.constants import VALID_BLOOD_GROUPS
from app.schemas.user.base import BaseSchema


class ProfileUpdateRequest(BaseSchema):
    """
    =========================================================
    PROFILE UPDATE REQUEST (ENTERPRISE + HEALTHCARE READY)
    =========================================================
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # =====================================================
    # BASIC PROFILE
    # =====================================================
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    bio: Optional[str] = Field(default=None, max_length=500)
    avatar_url: Optional[str] = Field(default=None, max_length=1000)
    cover_photo_url: Optional[str] = Field(default=None, max_length=1000)

    # =====================================================
    # CONTACT
    # =====================================================
    phone_number: Optional[str] = Field(default=None, max_length=30)
    emergency_contact: Optional[str] = Field(default=None, max_length=50)
    emergency_name: Optional[str] = Field(default=None, max_length=255)
    emergency_relationship: Optional[str] = Field(default=None, max_length=100)

    # =====================================================
    # PERSONAL
    # =====================================================
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    gender: Optional[str] = Field(default=None, max_length=30)
    birth_date: Optional[date] = None

    # =====================================================
    # LOCATION
    # =====================================================
    city: Optional[str] = Field(default=None, max_length=120)
    state: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, max_length=120)

    # =====================================================
    # LOCALIZATION
    # =====================================================
    language: Optional[str] = Field(default=None, max_length=20)
    timezone: Optional[str] = Field(default=None, max_length=120)

    # =====================================================
    # BLOOD DONATION SYSTEM
    # =====================================================
    blood_group: Optional[str] = Field(default=None, max_length=10)
    is_donor: Optional[bool] = None

    donation_count: Optional[int] = Field(default=None, ge=0)
    last_donation_at: Optional[date] = None

    # =====================================================
    # MEDICAL INFO
    # =====================================================
    medical_notes: Optional[str] = Field(default=None, max_length=2000)
    allergies: Optional[str] = Field(default=None, max_length=1000)
    chronic_conditions: Optional[str] = Field(default=None, max_length=1000)

    # =====================================================
    # NORMALIZATION (GLOBAL CLEANER)
    # =====================================================
    @field_validator(
        "username",
        "bio",
        "avatar_url",
        "cover_photo_url",
        "phone_number",
        "gender",
        "city",
        "state",
        "country",
        "language",
        "timezone",
        "medical_notes",
        "allergies",
        "chronic_conditions",
        "emergency_contact",
        "emergency_name",
        "emergency_relationship",
        "blood_group",
    )
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    # =====================================================
    # USERNAME VALIDATION
    # =====================================================
    @field_validator("username")
    @classmethod
    def validate_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.strip().lower()

        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._")

        if any(ch not in allowed for ch in value):
            raise ValueError("Username contains invalid characters")

        return value

    # =====================================================
    # PHONE VALIDATION
    # =====================================================
    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.strip()

        if len(value) < 6:
            raise ValueError("Invalid phone number")

        return value

    # =====================================================
    # BLOOD GROUP VALIDATION (ENTERPRISE SAFE)
    # =====================================================
    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.strip().upper().replace(" ", "")

        if value not in VALID_BLOOD_GROUPS:
            raise ValueError(
                "Invalid blood group. Must be one of: "
                + ", ".join(sorted(VALID_BLOOD_GROUPS))
            )

        return value