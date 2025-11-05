# app/schemas/transport_request.py
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class TransportRequestBase(BaseModel):
    requester_name: str
    phone: str
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    details: Optional[str] = None

class TransportRequestCreate(TransportRequestBase):
    pass

class TransportRequest(TransportRequestBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # for Pydantic v2