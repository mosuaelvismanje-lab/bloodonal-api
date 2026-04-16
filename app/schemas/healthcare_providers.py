from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from datetime import datetime
from app.models.healthcare_provider import ProviderType

# --- Base schema for common fields ---
class HealthcareProviderBase(BaseModel):
    """
    Base schema for Healthcare Providers.
    Geo-data (Lat/Lon) has been removed to support the Neon Async architecture.
    """
    model_config = ConfigDict(from_attributes=True)

    name: str
    city: str
    service_type: ProviderType
    phone: str
    email: Optional[EmailStr] = None
    is_active: bool = True


# --- Schema for creating a provider ---
class HealthcareProviderCreate(HealthcareProviderBase):
    """
    Inherits all fields from Base.
    Required for the 'Registration' flow.
    """
    pass


# --- Schema for updating a provider ---
class HealthcareProviderUpdate(BaseModel):
    """
    Used for PATCH/PUT updates.
    Allows changing status (is_active) or contact info independently.
    """
    name: Optional[str] = None
    city: Optional[str] = None
    service_type: Optional[ProviderType] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None


# --- Schema returned for Search/Autocomplete (Resolver) ---
class HealthcareProviderShort(BaseModel):
    """
    ✅ NEW: Minimal schema for the search dropdown.
    Returns only what the frontend needs to show a name and store an ID.
    """
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    service_type: ProviderType


# --- Schema returned from API (Full Response Model) ---
class HealthcareProvider(HealthcareProviderBase):
    """
    The full representation of a provider, including timestamps.
    """
    id: int
    created_at: datetime