from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.healthcare_provider import ProviderType

# --- Base schema for common fields ---
class HealthcareProviderBase(BaseModel):
    """
    Base schema for Healthcare Providers.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str
    city: str
    service_type: ProviderType
    phone: str
    email: Optional[EmailStr] = None
    is_active: bool = True
    # ✅ Unified field for Hospital Name, Lab Name, or Vehicle Plate
    hospital: str


# --- Schema for creating a provider ---
class HealthcareProviderCreate(HealthcareProviderBase):
    pass


# --- Schema for updating a provider ---
class HealthcareProviderUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    hospital: Optional[str] = None
    service_type: Optional[ProviderType] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


# --- Schema returned for Search/Autocomplete (Resolver) ---
class HealthcareProviderShort(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    hospital: str
    service_type: ProviderType


# --- Schema returned from API (Full Response Model) ---
class HealthcareProvider(HealthcareProviderBase):
    id: int
    created_at: datetime