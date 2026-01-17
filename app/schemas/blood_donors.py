from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime

BLOOD_TYPE_CHOICES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}

class BloodDonorBase(BaseModel):
    """
    Base schema for blood donors.
    Contains core fields and shared validation logic.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str
    phone: str
    blood_type: str
    city: Optional[str] = None
    hospital: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = True
    fcm_token: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        digits = "".join(filter(str.isdigit, v))
        if digits != v:
            raise ValueError("phone must contain digits only")
        if len(v) < 7 or len(v) > 15:
            raise ValueError("phone length seems invalid")
        return v

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in BLOOD_TYPE_CHOICES:
            raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPE_CHOICES)}")
        return v

class BloodDonorCreate(BloodDonorBase):
    """Schema for creating a donor; inherits all base fields and validators."""
    pass

class BloodDonorUpdate(BloodDonorBase):
    """
    Schema for updates. Inherits validators from Base.
    Fields are re-declared as Optional to allow partial updates.
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    blood_type: Optional[str] = None

class BloodDonor(BloodDonorBase):
    """
    The final model returned by the API.
    Inherits model_config and validators automatically.
    """
    id: int
    created_at: datetime
    updated_at: datetime
