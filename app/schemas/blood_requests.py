from datetime import datetime
from pydantic import BaseModel
from typing import Optional

class BloodRequestBase(BaseModel):
    requester_name: str
    city: str
    phone: str
    blood_type: str
    needed_units: int
    hospital: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    urgent: Optional[bool] = True

class BloodRequestCreate(BloodRequestBase):
    pass

class BloodRequest(BloodRequestBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # For ORM-to-Pydantic support
