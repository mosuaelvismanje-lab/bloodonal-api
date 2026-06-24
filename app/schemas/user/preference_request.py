# =========================================================
# FILE: app/schemas/user/preference_request.py
# =========================================================

from __future__ import annotations

from typing import Optional

from pydantic import (
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.base import BaseSchema


class PreferenceRequest(BaseSchema):
    """
    =========================================================
    USER PREFERENCE REQUEST DTO
    =========================================================
    Used for:
    - settings screen
    - notification controls
    - localization
    - accessibility
    - UI personalization
    =========================================================
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # =====================================================
    # APP EXPERIENCE
    # =====================================================
    language: Optional[str] = Field(
        default="en",
        max_length=20,
    )

    timezone: Optional[str] = Field(
        default="UTC",
        max_length=100,
    )

    theme: Optional[str] = Field(
        default="system",
        max_length=20,
    )

    # =====================================================
    # NOTIFICATIONS
    # =====================================================
    push_notifications_enabled: bool = True

    sms_notifications_enabled: bool = False

    email_notifications_enabled: bool = True

    marketing_notifications_enabled: bool = False

    emergency_alerts_enabled: bool = True

    # =====================================================
    # PRIVACY
    # =====================================================
    profile_visibility: Optional[str] = Field(
        default="public",
        max_length=20,
    )

    show_online_status: bool = True

    show_last_seen: bool = True

    allow_location_tracking: bool = True

    # =====================================================
    # ACCESSIBILITY
    # =====================================================
    large_text_enabled: bool = False

    reduced_motion_enabled: bool = False

    high_contrast_enabled: bool = False

    # =====================================================
    # VALIDATORS
    # =====================================================
    @field_validator(
        "language",
        "timezone",
        "theme",
        "profile_visibility",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        cleaned = value.strip().lower()

        return cleaned or None

    @field_validator("theme")
    @classmethod
    def validate_theme(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        allowed = {
            "light",
            "dark",
            "system",
        }

        if value not in allowed:
            raise ValueError("Invalid theme")

        return value

    @field_validator("profile_visibility")
    @classmethod
    def validate_visibility(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        allowed = {
            "public",
            "private",
            "friends",
        }

        if value not in allowed:
            raise ValueError(
                "Invalid profile visibility"
            )

        return value