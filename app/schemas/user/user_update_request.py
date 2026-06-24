# =========================================================
# FILE: app/schemas/user/user_update_request.py
# =========================================================

from __future__ import annotations

from typing import Optional

from pydantic import ConfigDict, Field, field_validator

from app.schemas.base import BaseSchema


class UserUpdateRequest(BaseSchema):
    """
    =========================================================
    USER UPDATE REQUEST DTO
    =========================================================
    Used for:
    - edit profile
    - onboarding
    - settings update
    - account customization
    =========================================================
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # =====================================================
    # BASIC PROFILE
    # =====================================================
    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=120,
    )

    # =====================================================
    # DEVICE INFO
    # =====================================================
    platform: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    device_model: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    app_version: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    # =====================================================
    # PUSH TOKEN
    # =====================================================
    fcm_token: Optional[str] = Field(
        default=None,
        max_length=512,
    )

    # =====================================================
    # VALIDATORS
    # =====================================================
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        cleaned = value.strip()

        if len(cleaned) < 2:
            raise ValueError("Name too short")

        return cleaned

    @field_validator(
        "platform",
        "device_model",
        "app_version",
        "fcm_token",
    )
    @classmethod
    def normalize_optional_text(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None