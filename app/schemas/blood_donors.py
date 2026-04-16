from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional
from datetime import datetime

# UPDATED: Included "UNKNOWN" in valid choices
BLOOD_TYPE_CHOICES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "UNKNOWN"}


class BloodDonorBase(BaseModel):
    """
    Base schema for blood donors.
    Updated to allow 'UNKNOWN' as a valid blood type.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str
    phone: str
    # UPDATED: Default set to "UNKNOWN"
    blood_type: str = "UNKNOWN"
    city: str
    hospital: Optional[str] = None
    is_active: bool = True
    fcm_token: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, v))
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("phone length must be between 7 and 15 digits")
        return digits

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: str) -> str:
        v_upper = v.upper()
        if v_upper not in BLOOD_TYPE_CHOICES:
            raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPE_CHOICES)}")
        return v_upper


class BloodDonorCreate(BloodDonorBase):
    """Schema for creating a donor; inherits all base fields and validators."""
    pass


class BloodDonorUpdate(BaseModel):
    """
    Schema for partial updates.
    """
    name: Optional[str] = None
    phone: Optional[str] = None
    blood_type: Optional[str] = None
    city: Optional[str] = None
    hospital: Optional[str] = None
    is_active: Optional[bool] = None
    fcm_token: Optional[str] = None

    @field_validator("phone", "blood_type", mode="before")
    @classmethod
    def validate_update_fields(cls, v):
        if v is None:
            return v
        # Ensure that if blood_type is updated, it's still checked against our choices
        if isinstance(v, str) and len(v) > 0:
            v_upper = v.upper()
            if "phone" in cls.__fields__ and v.isdigit(): # Basic check if it's the phone field
                 return v
            if v_upper not in BLOOD_TYPE_CHOICES:
                 raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPE_CHOICES)}")
            return v_upper
        return v


class BloodDonor(BloodDonorBase):
    """
    The final model returned by the API.
    """
    id: int
    created_at: datetime
    updated_at: datetime