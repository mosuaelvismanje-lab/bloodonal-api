from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class ServiceListingBase(BaseModel):
    """
    Base schema for all modular services (Blood, Taxi, Doctor, etc.)
    """
    service_type: str = Field(..., description="e.g., 'blood-request', 'taxi-request'")
    title: Optional[str] = Field(None, description="Human-readable title for the request")

    # ✅ Synchronized with the 'details' JSON column in your Model
    details: Dict[str, Any] = Field(
        default={},
        description="Service-specific data (e.g., blood_group, destination)"
    )


class ServiceListingCreate(ServiceListingBase):
    """
    Used when creating a new service request.
    The Orchestrator will use this to build the initial ServiceListing.
    """
    user_id: str
    # Usually set by the Orchestrator/Model, but can be overridden
    expires_at: Optional[datetime] = None


class ServiceListingResponse(ServiceListingBase):
    """
    The polymorphic response returned to the Mobile/Web UI.
    Includes the 'Switches' set by the Orchestrator.
    """
    id: int
    user_id: str
    provider_id: Optional[str] = None
    status: str
    is_published: bool
    is_paid: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    # ✅ Pydantic V2 configuration replacing 'class Config'
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


# ✅ Logic for the "Provider" side of the app
class ServiceAcceptRequest(BaseModel):
    """
    Payload for when a Doctor, Donor, or Driver accepts a listing.
    """
    provider_id: str