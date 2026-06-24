from __future__ import annotations

from uuid import UUID
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import Field, AliasChoices, field_validator, computed_field

from app.modules.blood.common.base_schema import BaseSchema
from app.modules.blood.domain.constants import VALID_BLOOD_GROUPS


DONATION_COOLDOWN_DAYS = 90


# =========================================================
# DONOR CREATE
# =========================================================
class DonorCreate(BaseSchema):
    full_name: str = Field(
        validation_alias=AliasChoices("fullName", "full_name")
    )
    phone: str
    city: str
    blood_group: str = Field(
        validation_alias=AliasChoices("bloodGroup", "blood_group")
    )

    is_available: bool = True

    referral_code: Optional[str] = None
    referred_by: Optional[str] = None
    fcm_token: Optional[str] = None

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v: str):
        v = v.strip().upper()
        if v not in VALID_BLOOD_GROUPS:
            raise ValueError("Invalid blood group")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str):
        v = v.strip()
        if len(v) < 8:
            raise ValueError("Invalid phone number")
        return v

    @field_validator("city")
    @classmethod
    def normalize_city(cls, v: str):
        return v.strip().lower()


# =========================================================
# DONOR UPDATE
# =========================================================
class DonorUpdate(BaseSchema):
    full_name: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("fullName", "full_name"),
    )
    phone: Optional[str] = None
    city: Optional[str] = None
    blood_group: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("bloodGroup", "blood_group"),
    )
    is_available: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("isAvailable", "is_available"),
    )

    referral_code: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("referralCode", "referral_code"),
    )
    referred_by: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("referredBy", "referred_by"),
    )
    fcm_token: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("fcmToken", "fcm_token"),
    )

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if v not in VALID_BLOOD_GROUPS:
            raise ValueError("Invalid blood group")
        return v

    @field_validator("city")
    @classmethod
    def normalize_city(cls, v):
        return v.strip().lower() if v else v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        v = v.strip()
        if len(v) < 8:
            raise ValueError("Invalid phone number")
        return v


# =========================================================
# DONOR RESPONSE (API DTO)
# =========================================================
class DonorResponse(BaseSchema):
    model_config = BaseSchema.model_config | {
        "from_attributes": True,
        "frozen": True,
        "populate_by_name": True,
    }

    id: UUID
    full_name: str
    phone: str
    city: str
    blood_group: str

    is_available: bool
    is_active: bool

    fcm_token: Optional[str]

    points: int
    total_donations: int
    successful_responses: int
    rejection_count: int
    rank_level: str

    referral_code: Optional[str]
    referred_by: Optional[str]

    last_donation_date: Optional[datetime]

    created_at: datetime
    updated_at: Optional[datetime]

    match_score: Optional[int] = None
    priority: Optional[str] = None

    @computed_field
    @property
    def next_eligible_date(self) -> Optional[datetime]:
        if not self.last_donation_date:
            return None
        return self.last_donation_date + timedelta(days=DONATION_COOLDOWN_DAYS)

    @computed_field
    @property
    def is_eligible_to_donate(self) -> bool:
        if not self.last_donation_date:
            return True

        now = datetime.now(timezone.utc)
        return now - self.last_donation_date >= timedelta(
            days=DONATION_COOLDOWN_DAYS
        )

    @computed_field
    @property
    def donation_cooldown_remaining_days(self) -> int:
        if not self.last_donation_date:
            return 0

        elapsed = datetime.now(timezone.utc) - self.last_donation_date
        remaining = DONATION_COOLDOWN_DAYS - elapsed.days
        return max(0, remaining)

    @computed_field
    @property
    def rank_label(self) -> str:
        return self.rank_level