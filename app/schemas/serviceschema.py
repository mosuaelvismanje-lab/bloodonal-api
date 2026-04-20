from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


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
    """
    user_id: UUID
    expires_at: Optional[datetime] = None


class ServiceListingResponse(ServiceListingBase):
    """
    The polymorphic response returned to the Mobile/Web UI.
    """
    id: UUID
    user_id: UUID
    provider_id: Optional[UUID] = None
    status: str
    is_published: bool
    is_paid: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


# ✅ FIXED: Added SearchItemOut for the Global Search Engine
class SearchItemOut(BaseModel):
    """
    Unified search result schema.
    Used to display both Users (Providers) and Requests in one list.
    """
    id: str
    title: str
    subtitle: str
    type: str = Field(..., description="'provider' or 'listing'")
    imageUrl: Optional[str] = None
    category: str = Field(..., description="e.g., 'nurse', 'blood-request', 'emergency'")

    model_config = ConfigDict(from_attributes=True)


# ✅ Logic for the "Provider" side of the app
class ServiceAcceptRequest(BaseModel):
    """
    Payload for when a Doctor, Donor, or Driver accepts a listing.
    """
    provider_id: str