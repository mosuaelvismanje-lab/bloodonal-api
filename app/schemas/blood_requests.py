from datetime import datetime
from pydantic import BaseModel, ConfigDict # ✅ Added ConfigDict
from typing import Optional

class BloodRequestBase(BaseModel):
    # ✅ Set config at the base level so all children inherit it
    model_config = ConfigDict(from_attributes=True)

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
    # ❌ REMOVED: class Config: from_attributes = True
