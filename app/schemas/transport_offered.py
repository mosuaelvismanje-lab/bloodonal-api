from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional


class TransportOfferBase(BaseModel):
    """
    Base schema for transport offers.
    Shared by Create and Response models.
    """
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    provider_name: str
    phone: str
    capacity: Optional[int] = None
    details: Optional[str] = None

    # --- Geolocation fields (latitude/longitude) have been removed ---

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Basic validation to ensure phone contains only digits/standard characters
        digits = "".join(filter(str.isdigit, v))
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError("Phone number must be between 7 and 15 digits")
        return digits


class TransportOfferCreate(TransportOfferBase):
    """
    Schema used for incoming POST requests to create a new offer.
    """
    pass


class TransportOfferUpdate(BaseModel):
    """
    Schema for partial updates (PATCH/PUT).
    All fields are optional.
    """
    provider_name: Optional[str] = None
    phone: Optional[str] = None
    capacity: Optional[int] = None
    details: Optional[str] = None


class TransportOffer(TransportOfferBase):
    """
    The final model returned by the API (Response Model).
    """
    id: int
    created_at: datetime