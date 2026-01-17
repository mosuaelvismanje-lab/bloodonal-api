from pydantic import BaseModel, ConfigDict  # ✅ Added ConfigDict
from typing import Optional
from datetime import datetime
from app.models.healthcare_provider import ProviderType


class HealthcareRequestBase(BaseModel):
    # ✅ Set config at the base so Create and Request both inherit it
    model_config = ConfigDict(from_attributes=True)

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
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    service_type: Optional[ProviderType] = None


class HealthcareRequest(HealthcareRequestBase):
    id: int
    created_at: datetime
    provider: Optional[HealthcareProviderInfo] = None

    # ❌ REMOVED: class Config block (now inherited from HealthcareRequestBase)
