from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class TransportRequestBase(BaseModel):
    """
    Base schema for transport requests.
    Using model_config here ensures all children support ORM mapping.
    """
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    requester_name: str
    phone: str

    # --- Geolocation fields (pickup/dropoff lat/lon) have been removed ---

    details: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Standardize phone format by keeping only digits
        digits = "".join(filter(str.isdigit, v))
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone number must be between 7 and 15 digits")
        return digits


class TransportRequestCreate(TransportRequestBase):
    """
    Used for incoming creation data (POST requests).
    """
    pass


class TransportRequestUpdate(BaseModel):
    """
    Used for partial updates (PATCH/PUT).
    Allows updating specific fields without requiring the whole object.
    """
    requester_name: Optional[str] = None
    phone: Optional[str] = None
    details: Optional[str] = None


class TransportRequest(TransportRequestBase):
    """
    Used for outgoing data, typically returned from the database.
    """
    id: int
    created_at: datetime