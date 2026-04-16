from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator, Field
from typing import Optional

# ✅ Standardized Blood Type Choices
BLOOD_TYPE_CHOICES = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
# ✅ Standardized Request Statuses
STATUS_CHOICES = {"PENDING", "FULFILLED", "EXPIRED", "CANCELLED"}

class BloodRequestBase(BaseModel):
    """
    Base schema for blood requests.
    Shared fields between Creation and Response models.
    """
    requester_name: str = Field(..., min_length=2, max_length=100)
    city: str = Field(..., min_length=2, max_length=50)
    phone: str = Field(..., description="Contact number for the requester")
    blood_type: str
    needed_units: int = Field(default=1, ge=1, le=50)
    hospital: Optional[str] = Field(None, max_length=150)
    urgent: bool = True

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v: str) -> str:
        """Ensures blood type matches standard medical notation and is uppercase."""
        v_upper = v.upper().strip()
        if v_upper not in BLOOD_TYPE_CHOICES:
            raise ValueError(f"blood_type must be one of {sorted(BLOOD_TYPE_CHOICES)}")
        return v_upper

class BloodRequestCreate(BloodRequestBase):
    """
    Incoming data from the Mobile App.
    user_id is omitted here as it is extracted from the Auth token by the backend.
    """
    pass

class BloodRequestUpdate(BaseModel):
    """
    ✅ NEW: Used for modular status updates or toggling urgency.
    Allows the Service layer to mark requests as FULFILLED or EXPIRED.
    """
    status: Optional[str] = None
    urgent: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v:
            v_upper = v.upper().strip()
            if v_upper not in STATUS_CHOICES:
                raise ValueError(f"status must be one of {STATUS_CHOICES}")
            return v_upper
        return v

class BloodRequest(BloodRequestBase):
    """
    The final model returned to the Android app (Response Model).
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    status: str = "PENDING"
    created_at: datetime
    # Useful for tracking when a request was fulfilled
    updated_at: Optional[datetime] = None