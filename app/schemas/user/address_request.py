# =========================================================
# FILE: app/schemas/user/address_request.py
# =========================================================

from __future__ import annotations

from typing import Optional

from pydantic import (
    ConfigDict,
    Field,
    field_validator,
)

from app.schemas.base import BaseSchema


class AddressRequest(BaseSchema):
    """
    =========================================================
    ADDRESS REQUEST DTO
    =========================================================
    Used for:
    - delivery systems
    - emergency services
    - healthcare logistics
    - ambulance dispatch
    - donor routing
    =========================================================
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # =====================================================
    # LABEL
    # =====================================================
    label: Optional[str] = Field(
        default="home",
        max_length=50,
    )

    # =====================================================
    # ADDRESS
    # =====================================================
    address_line_1: str = Field(
        ...,
        min_length=3,
        max_length=255,
    )

    address_line_2: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    landmark: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    city: str = Field(
        ...,
        min_length=2,
        max_length=120,
    )

    state: Optional[str] = Field(
        default=None,
        max_length=120,
    )

    postal_code: Optional[str] = Field(
        default=None,
        max_length=30,
    )

    country: str = Field(
        ...,
        min_length=2,
        max_length=120,
    )

    # =====================================================
    # GPS
    # =====================================================
    latitude: Optional[float] = None

    longitude: Optional[float] = None

    # =====================================================
    # FLAGS
    # =====================================================
    is_default: bool = False

    # =====================================================
    # VALIDATORS
    # =====================================================
    @field_validator(
        "label",
        "address_line_1",
        "address_line_2",
        "landmark",
        "city",
        "state",
        "postal_code",
        "country",
    )
    @classmethod
    def normalize_text(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None

    @field_validator("latitude")
    @classmethod
    def validate_latitude(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is None:
            return None

        if value < -90 or value > 90:
            raise ValueError("Invalid latitude")

        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(
        cls,
        value: Optional[float],
    ) -> Optional[float]:
        if value is None:
            return None

        if value < -180 or value > 180:
            raise ValueError("Invalid longitude")

        return value