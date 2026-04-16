from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from app.models.healthcare_provider import ProviderType


class HealthcareRequestBase(BaseModel):
    """
    Base schema for healthcare requests.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "requester_name": "Mich B",
                "phone": "670123456",
                "city": "Limbe",
                "description": "Patient needs home nursing care.",
                "assigned_provider_id": None,
                "status": "pending"
            }
        }
    )

    requester_name: str
    phone: str
    city: str
    description: Optional[str] = None
    assigned_provider_id: Optional[int] = Field(default=None)
    status: Optional[str] = Field(default="pending")


class HealthcareRequestCreate(HealthcareRequestBase):
    """
    Used when a patient submits a new request.
    """
    pass


class HealthcareProviderInfo(BaseModel):
    """
    Simplified provider info returned to the user.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    service_type: Optional[ProviderType] = None
    phone: Optional[str] = None


class HealthcareRequest(HealthcareRequestBase):
    """
    The final representation of a request returned by the API.
    Includes timestamps for the request lifecycle.
    """
    id: int
    created_at: datetime

    # ✅ Added these to show the automatic status timing to the user
    assigned_at: Optional[datetime] = None
    updated_at: datetime

    # Populated by SQLAlchemy 'selectin' loading
    provider: Optional[HealthcareProviderInfo] = None