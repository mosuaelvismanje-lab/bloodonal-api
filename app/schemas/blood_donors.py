from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime

BLOOD_TYPE_CHOICES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}

class BloodDonorBase(BaseModel):
    name: str
    phone: str
    blood_type: str
    city: Optional[str] = None
    hospital: Optional[str] = None        # ← new field
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = True
    fcm_token: Optional[str] = None

    # Pydantic v2 ORM mode
    model_config = ConfigDict(from_attributes=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if digits != v:
            raise ValueError("phone must contain digits only")
        if len(v) < 7 or len(v) > 15:
            raise ValueError("phone length seems invalid")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: str) -> str:
        if v not in BLOOD_TYPE_CHOICES:
            raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPE_CHOICES)}")
        return v

class BloodDonorCreate(BloodDonorBase):
    """Schema for creating a donor; inherits hospital field."""

class BloodDonorUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    blood_type: Optional[str] = None
    hospital: Optional[str] = None        # ← new field
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None
    fcm_token: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if digits != v:
            raise ValueError("phone must contain digits only")
        if len(v) < 7 or len(v) > 15:
            raise ValueError("phone length seems invalid")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: str) -> str:
        if v not in BLOOD_TYPE_CHOICES:
            raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPE_CHOICES)}")
        return v

class BloodDonor(BloodDonorBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
