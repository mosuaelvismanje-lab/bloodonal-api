from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class TransportOfferBase(BaseModel):
    provider_name: str
    phone: str
    available_latitude: float
    available_longitude: float
    capacity: Optional[int] = None
    details: Optional[str] = None

class TransportOfferCreate(TransportOfferBase):
    pass

class TransportOffer(TransportOfferBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
