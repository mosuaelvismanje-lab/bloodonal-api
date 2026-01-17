from datetime import datetime
from pydantic import BaseModel, ConfigDict  # ✅ Added ConfigDict
from typing import Optional


class TransportOfferBase(BaseModel):
    """
    Base schema for transport offers.
    By setting model_config here, all children inherit ORM support.
    """
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    provider_name: str
    phone: str
    available_latitude: float
    available_longitude: float
    capacity: Optional[int] = None
    details: Optional[str] = None


class TransportOfferCreate(TransportOfferBase):
    """Used for incoming data when creating a new offer."""
    pass


class TransportOffer(TransportOfferBase):
    """Used for outgoing data, including database-generated fields."""
    id: int
    created_at: datetime

    # ❌ REMOVED: class Config block is no longer needed
