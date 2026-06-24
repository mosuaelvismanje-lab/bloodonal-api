from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# BASE CONFIG
# =========================================================
BASE_MODEL_CONFIG = ConfigDict(
    populate_by_name=False,
    extra="ignore",
    from_attributes=True,
)


# =========================================================
# ENUMS
# =========================================================
class ServiceType(str, Enum):
    HEALTHCARE = "healthcare"
    BLOOD = "blood"
    TRANSPORT = "transport"
    AMBULANCE = "ambulance"
    DONOR = "donor"


class DispatchStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    URGENT = "URGENT"


class DispatchEventType(str, Enum):
    REQUEST_ASSIGNED = "request_assigned"
    REQUEST_UPDATED = "request_updated"
    LOCATION_UPDATED = "location_updated"
    REQUEST_CREATED = "request_created"
    REQUEST_CANCELLED = "request_cancelled"
    HEARTBEAT = "heartbeat"


# =========================================================
# QUERY SCHEMA
# =========================================================
class DispatchQuerySchema(BaseModel):
    """
    Internal query schema.
    Uses snake_case ONLY internally.
    """

    model_config = BASE_MODEL_CONFIG

    service_type: str
    latitude: float
    longitude: float
    radius_km: float = 50.0
    blood_group: Optional[str] = None
    limit: int = 200
    include_clusters: bool = False
    cluster_precision_km: float = 1.0


# =========================================================
# NEARBY REQUEST DTO
# =========================================================
class NearbyRequestDTO(BaseModel):
    """
    Internal snake_case.
    External API serialized via aliases.
    """

    model_config = BASE_MODEL_CONFIG

    id: str

    patient_name: str = Field(
        default="Unknown",
        serialization_alias="patientName",
    )

    blood_group: str = Field(
        default="Unknown",
        serialization_alias="bloodGroup",
    )

    needed_units: int = Field(
        default=0,
        serialization_alias="neededUnits",
    )

    city: str = "Unknown"

    latitude: float = 0.0
    longitude: float = 0.0

    is_urgent: bool = Field(
        default=False,
        serialization_alias="isUrgent",
    )

    service_type: str = Field(
        default="unknown",
        serialization_alias="serviceType",
    )

    distance_km: float = Field(
        default=0.0,
        serialization_alias="distanceKm",
    )

    urgency_score: float = Field(
        default=0.0,
        serialization_alias="urgencyScore",
    )

    blood_match_score: float = Field(
        default=0.0,
        serialization_alias="bloodMatchScore",
    )

    relevance_score: float = Field(
        default=0.0,
        serialization_alias="relevanceScore",
    )


class NearbyRequestsResponse(BaseModel):
    model_config = BASE_MODEL_CONFIG

    items: list[NearbyRequestDTO]


# =========================================================
# CLUSTER DTO
# =========================================================
class ClusterItemDTO(BaseModel):
    """
    Strongly typed cluster DTO.
    Repository/service should return this directly.
    """

    model_config = BASE_MODEL_CONFIG

    cluster_id: str = Field(
        serialization_alias="clusterId",
    )

    count: int
    urgent: int
    latitude: float
    longitude: float


class ClusterResponse(BaseModel):
    model_config = BASE_MODEL_CONFIG

    items: list[ClusterItemDTO]


# =========================================================
# ASSIGNMENT DTOs
# =========================================================
class AssignmentRequestSchema(BaseModel):
    """
    Accept camelCase externally.
    Store internally as snake_case.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )

    request_id: str = Field(
        validation_alias="requestId",
        serialization_alias="requestId",
    )

    donor_id: Optional[str] = Field(
        default=None,
        validation_alias="donorId",
        serialization_alias="donorId",
    )


class AssignmentResultDTO(BaseModel):
    """
    Avoid hidden empty-string bugs.
    """

    model_config = BASE_MODEL_CONFIG

    assigned: bool = False

    request_id: Optional[str] = Field(
        default=None,
        serialization_alias="requestId",
    )

    donor_id: Optional[str] = Field(
        default=None,
        serialization_alias="donorId",
    )

    score: Optional[float] = None

    eta_minutes: Optional[int] = Field(
        default=None,
        serialization_alias="etaMinutes",
    )

    reason: Optional[str] = None


class AssignmentResponse(BaseModel):
    model_config = BASE_MODEL_CONFIG

    result: AssignmentResultDTO


# =========================================================
# LOCATION DTO
# =========================================================
class LocationUpdateDTO(BaseModel):
    """
    Public API accepts camelCase.
    Internal usage remains snake_case.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )

    user_id: str = Field(
        validation_alias="userId",
        serialization_alias="userId",
    )

    latitude: float
    longitude: float

    service_type: str = Field(
        validation_alias="serviceType",
        serialization_alias="serviceType",
    )

    is_available: bool = Field(
        default=True,
        validation_alias="isAvailable",
        serialization_alias="isAvailable",
    )


# =========================================================
# REALTIME EVENT DTO
# =========================================================
class DispatchEventDTO(BaseModel):
    """
    Timestamp flexibility for websocket/router normalization.
    """

    model_config = BASE_MODEL_CONFIG

    event: str

    # allows router/service ISO string OR datetime
    timestamp: datetime | str

    data: dict[str, Any]


class DispatchEventResponse(BaseModel):
    """
    Generic event response wrapper.
    """

    model_config = BASE_MODEL_CONFIG

    event: DispatchEventDTO


# =========================================================
# LOCATION RESPONSE
# =========================================================
class LocationUpdateResponse(BaseModel):
    model_config = BASE_MODEL_CONFIG

    event: DispatchEventDTO