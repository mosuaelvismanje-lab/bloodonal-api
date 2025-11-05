from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.healthcare_provider import ProviderType  # import the enum

class HealthcareRequestBase(BaseModel):
    requester_name: str
    phone: str
    city: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    assigned_provider_id: Optional[int] = None
    status: Optional[str] = "pending"

class HealthcareRequestCreate(HealthcareRequestBase):
    pass

# Optional nested provider info
class HealthcareProviderInfo(BaseModel):
    id: int
    name: str
    service_type: Optional[ProviderType] = None

    class Config:
        from_attributes = True

class HealthcareRequest(HealthcareRequestBase):
    id: int
    created_at: datetime
    provider: Optional[HealthcareProviderInfo] = None  # Nested provider info

    class Config:
        from_attributes = True  # For ORM integration
