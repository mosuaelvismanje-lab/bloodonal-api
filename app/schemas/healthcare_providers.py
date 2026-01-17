from pydantic import BaseModel, Field, EmailStr, ConfigDict  # ✅ Added ConfigDict
from typing import Optional
from datetime import datetime
from enum import Enum


# Enum for provider types
class ProviderType(str, Enum):
    doctor = "doctor"
    nurse = "nurse"
    lab = "lab"


# --- Base schema for common fields ---
class HealthcareProviderBase(BaseModel):
    # ✅ Modern Pydantic V2 configuration
    # By placing it here, Create, Update, and the final model all inherit ORM support
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    city: Optional[str] = None
    service_type: Optional[ProviderType] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = True


# --- Schema for creating a provider ---
class HealthcareProviderCreate(HealthcareProviderBase):
    name: str
    service_type: ProviderType
    phone: str


# --- Schema for updating a provider (all fields optional) ---
class HealthcareProviderUpdate(HealthcareProviderBase):
    pass


# --- Schema returned from API ---
class HealthcareProvider(HealthcareProviderBase):
    id: int
    created_at: datetime
    # ❌ REMOVED: class Config block is no longer needed
