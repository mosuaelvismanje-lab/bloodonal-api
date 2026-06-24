# =========================================================
# FILE: app/schemas/user/address_response.py
# =========================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, computed_field

from app.schemas.base import BaseSchema


class AddressResponse(BaseSchema):
    """
    =========================================================
    ADDRESS RESPONSE DTO
    =========================================================
    Safe for:
    - mobile frontend
    - dispatch engines
    - admin dashboard
    - maps integration
    =========================================================
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    # =====================================================
    # IDS
    # =====================================================
    id: UUID

    user_id: UUID

    # =====================================================
    # LABEL
    # =====================================================
    label: Optional[str] = None

    # =====================================================
    # ADDRESS
    # =====================================================
    address_line_1: str

    address_line_2: Optional[str] = None

    landmark: Optional[str] = None

    city: str

    state: Optional[str] = None

    postal_code: Optional[str] = None

    country: str

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
    # AUDIT
    # =====================================================
    created_at: datetime

    updated_at: Optional[datetime] = None

    # =====================================================
    # COMPUTED
    # =====================================================
    @computed_field
    @property
    def full_address(self) -> str:
        """
        Frontend-safe full formatted address.
        """

        parts = [
            self.address_line_1,
            self.address_line_2,
            self.landmark,
            self.city,
            self.state,
            self.postal_code,
            self.country,
        ]

        return ", ".join(
            str(part).strip()
            for part in parts
            if part
        )