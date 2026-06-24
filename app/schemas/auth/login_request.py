from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    """
    =========================================================
    AUTH LOGIN REQUEST
    =========================================================
    Used for:
    - Firebase login sync
    - JWT bootstrap
    - Device registration
    - Session initialization
    =========================================================
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # =====================================================
    # AUTH
    # =====================================================
    auth_uid: str = Field(..., min_length=1, max_length=255)

    email: str = Field(..., min_length=3, max_length=255)

    name: str = Field(..., min_length=1, max_length=255)

    # =====================================================
    # DEVICE
    # =====================================================
    platform: Optional[str] = Field(default=None, max_length=50)

    device_id: Optional[str] = Field(default=None, max_length=255)

    device_model: Optional[str] = Field(default=None, max_length=255)

    app_version: Optional[str] = Field(default=None, max_length=50)

    # =====================================================
    # PUSH
    # =====================================================
    fcm_token: Optional[str] = Field(default=None, max_length=512)

    # =====================================================
    # VALIDATORS
    # =====================================================
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("name cannot be empty")

        return cleaned

    @field_validator(
        "platform",
        "device_id",
        "device_model",
        "app_version",
        "fcm_token",
    )
    @classmethod
    def normalize_optional(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None