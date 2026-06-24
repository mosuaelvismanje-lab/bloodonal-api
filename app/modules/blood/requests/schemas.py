from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import AliasChoices, Field, field_validator

from app.modules.blood.common.base_schema import BaseSchema
from app.modules.blood.domain.constants import VALID_BLOOD_GROUPS
from app.modules.blood.domain.enum import BloodRequestStatusEnum


# =========================================================
# BASE SCHEMA
# =========================================================
class BloodRequestBase(BaseSchema):
    model_config = BaseSchema.model_config | {
        "populate_by_name": True,
    }

    patient_name: str = Field(
        ...,
        min_length=2,
        max_length=120,
        validation_alias=AliasChoices("patientName", "patient_name"),
    )
    phone: str = Field(
        ...,
        min_length=6,
        max_length=20,
        validation_alias=AliasChoices("phone", "phoneNumber"),
    )
    city: str = Field(
        ...,
        min_length=2,
        max_length=80,
        validation_alias=AliasChoices("city", "town"),
    )

    blood_group: str = Field(
        ...,
        min_length=2,
        max_length=3,
        validation_alias=AliasChoices("bloodGroup", "blood_group"),
    )
    hospital_location: str = Field(
        ...,
        min_length=3,
        max_length=255,
        validation_alias=AliasChoices(
            "hospitalLocation",
            "hospital_location",
        ),
    )

    needed_units: int = Field(
        default=1,
        ge=1,
        le=10,
        validation_alias=AliasChoices("neededUnits", "needed_units"),
    )

    urgency_level: int = Field(
        default=1,
        ge=1,
        le=4,
        validation_alias=AliasChoices("urgencyLevel", "urgency_level"),
    )

    # Legacy compatibility only.
    # The frontend should prefer urgencyLevel.
    is_urgent: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("isUrgent", "is_urgent"),
    )

    offer: str = Field(
        default="Voluntary",
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("offer", "offer"),
    )

    user_id: UUID = Field(
        validation_alias=AliasChoices("userId", "user_id"),
    )

    incentive_amount: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("incentiveAmount", "incentive_amount"),
    )

    # =====================================================
    # VALIDATION
    # =====================================================
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[0-9+]{6,20}", v):
            raise ValueError("Invalid phone format")
        return v

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in VALID_BLOOD_GROUPS:
            raise ValueError("Invalid blood group")
        return v

    @field_validator("city")
    @classmethod
    def normalize_city(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("urgency_level")
    @classmethod
    def validate_urgency_level(cls, v: int) -> int:
        if v < 1 or v > 4:
            raise ValueError("urgency_level must be between 1 and 4")
        return v


# =========================================================
# CREATE CONTRACT
# =========================================================
class BloodRequestCreate(BloodRequestBase):
    """Strict creation contract."""
    pass


# =========================================================
# UPDATE CONTRACT (PATCH SAFE)
# =========================================================
class BloodRequestUpdate(BaseSchema):
    model_config = BaseSchema.model_config | {
        "populate_by_name": True,
    }

    phone: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("phone", "phoneNumber"),
    )
    city: Optional[str] = None
    hospital_location: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "hospitalLocation",
            "hospital_location",
        ),
    )

    needed_units: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("neededUnits", "needed_units"),
    )

    urgency_level: Optional[int] = Field(
        default=None,
        ge=1,
        le=4,
        validation_alias=AliasChoices("urgencyLevel", "urgency_level"),
    )

    # Legacy compatibility only.
    is_urgent: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("isUrgent", "is_urgent"),
    )

    offer: Optional[str] = None
    incentive_amount: Optional[int] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("incentiveAmount", "incentive_amount"),
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not re.fullmatch(r"[0-9+]{6,20}", v):
            raise ValueError("Invalid phone format")
        return v

    @field_validator("city")
    @classmethod
    def normalize_city(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v

    @field_validator("urgency_level")
    @classmethod
    def validate_urgency_level(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 1 or v > 4:
            raise ValueError("urgency_level must be between 1 and 4")
        return v


# =========================================================
# RESPONSE CONTRACT (SOURCE OF TRUTH)
# =========================================================
class BloodRequestResponse(BaseSchema):
    model_config = BaseSchema.model_config | {
        "from_attributes": True,
        "frozen": True,
        "use_enum_values": True,
        "populate_by_name": True,
    }

    # CORE IDS
    id: UUID
    user_id: UUID

    # PATIENT INFO
    patient_name: str
    phone: str
    city: str

    # MEDICAL INFO
    blood_group: str
    hospital_location: str
    needed_units: int

    # STATUS / URGENCY
    status: BloodRequestStatusEnum
    urgency_level: int = 1
    is_urgent: Optional[bool] = None

    offer: str
    incentive_amount: int = 0

    # TIMELINE
    created_at: datetime
    updated_at: Optional[datetime]
    expires_at: datetime

    accepted_by: Optional[UUID]
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]

    # ANALYTICS STORED IN DB
    total_matches_sent: int = 0
    total_views: int = 0

    # =====================================================
    # DASHBOARD / UI FIELDS
    # =====================================================
    distance_km: float = 0.0
    active_offers: int = 0
    compatibility_percent: int = 0

    # =====================================================
    # DERIVED (SERVICE LAYER ONLY - NOT DB STORED)
    # =====================================================
    is_expired: bool = False
    is_cancelled: bool = False

    total_matches_found: int = 0
    top_match_score: int = 0

    reward_points_awarded: int = 0
    donor_rank_after: Optional[str] = None

    geo_distance_km: Optional[float] = None
    hospital_priority_score: Optional[int] = None
    emergency_override: bool = False

    # =====================================================
    # OPTIMISTIC LOCKING
    # =====================================================
    version: int = 1

    # =====================================================
    # SAFE COERCIONS
    # =====================================================
    @field_validator(
        "incentive_amount",
        "total_matches_sent",
        "total_views",
        "version",
        "distance_km",
        "active_offers",
        "compatibility_percent",
        "total_matches_found",
        "top_match_score",
        "reward_points_awarded",
        "hospital_priority_score",
        mode="before",
    )
    @classmethod
    def _default_number(cls, v):
        if v is None:
            return 0
        return v

    @field_validator("urgency_level", mode="before")
    @classmethod
    def _default_urgency(cls, v):
        if v is None:
            return 1
        return v

    @field_validator("created_at", "expires_at", mode="before")
    @classmethod
    def _reject_missing_datetime(cls, v):
        if v is None:
            raise ValueError("required datetime field is missing")
        return v