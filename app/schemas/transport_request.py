from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict  # ✅ Added ConfigDict


class TransportRequestBase(BaseModel):
    """
    Base schema for transport requests.
    Using model_config here ensures all children support ORM mapping.
    """
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    requester_name: str
    phone: str
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    details: Optional[str] = None


class TransportRequestCreate(TransportRequestBase):
    """Used for incoming creation data."""
    pass


class TransportRequest(TransportRequestBase):
    """Used for outgoing data, typically returned from the database."""
    id: int
    created_at: datetime

    # ❌ REMOVED: class Config block is no longer required
