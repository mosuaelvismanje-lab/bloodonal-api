from pydantic import BaseModel, Field, EmailStr
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

    class Config:
        from_attributes = True  # ORM mode for SQLAlchemy
