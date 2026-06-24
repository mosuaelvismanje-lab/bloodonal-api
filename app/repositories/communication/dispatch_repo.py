from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    computed_field,
)

# =========================================================
# ENTERPRISE CONSTANTS
# =========================================================

VALID_BLOOD_GROUPS: frozenset[str] = frozenset({
    "O-",
    "O+",
    "A-",
    "A+",
    "B-",
    "B+",
    "AB-",
    "AB+",
})

MAX_RADIUS_KM = 500.0
DEFAULT_RADIUS_KM = 50.0
DEFAULT_LIMIT = 200

# =========================================================
# ENUMS
# =========================================================


class DispatchEventType(str, Enum):
    LOCATION_UPDATED = "location.updated"
    REQUEST_CREATED = "request.created"
    REQUEST_UPDATED = "request.updated"
    REQUEST_ASSIGNED = "request.assigned"
    REQUEST_CANCELLED = "request.cancelled"
    REQUEST_COMPLETED = "request.completed"


class DispatchStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    EMERGENCY = "EMERGENCY"
    CRITICAL = "CRITICAL"


class ServiceType(str, Enum):
    BLOOD = "blood"
    AMBULANCE = "ambulance"
    TRANSPORT = "transport"
    PHARMACY = "pharmacy"
    LAB = "lab"
    DOCTOR = "doctor"
    NURSE = "nurse"
    HEALTHCARE = "healthcare"


# =========================================================
# BASE SCHEMA
# =========================================================


class DispatchBaseSchema(BaseModel):
    """
    Enterprise-safe base schema.

    Enforces:
    - strict serialization
    - ORM compatibility
    - immutable-safe validation
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        validate_assignment=True,
        extra="ignore",
        str_strip_whitespace=True,
        use_enum_values=True,
        frozen=False,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
    )


# =========================================================
# GEO LOCATION
# =========================================================


class GeoLocationSchema(DispatchBaseSchema):
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude coordinate",
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude coordinate",
    )


# =========================================================
# DISPATCH QUERY INPUT
# =========================================================


class DispatchQuerySchema(GeoLocationSchema):
    """
    Input schema for nearby dispatch queries.
    """

    service_type: ServiceType

    radius_km: float = Field(
        default=DEFAULT_RADIUS_KM,
        gt=0,
        le=MAX_RADIUS_KM,
    )

    blood_group: Optional[str] = None

    limit: int = Field(
        default=DEFAULT_LIMIT,
        gt=0,
        le=1000,
    )

    include_clusters: bool = False

    cluster_precision_km: float = Field(
        default=1.0,
        gt=0,
        le=25,
    )

    @field_validator("blood_group")
    @classmethod
    def validate_blood_group(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None:
            return None

        normalized = value.strip().upper()

        if normalized not in VALID_BLOOD_GROUPS:
            raise ValueError(
                f"Invalid blood group: {normalized}"
            )

        return normalized


# =========================================================
# LIVE MAP REQUEST DTO
# =========================================================


class NearbyRequestDTO(GeoLocationSchema):
    """
    Frontend-safe Uber map request DTO.
    """

    id: str

    patient_name: str = Field(
        default="Unknown",
        alias="patientName",
    )

    blood_group: str = Field(
        default="Unknown",
        alias="bloodGroup",
    )

    needed_units: int = Field(
        default=0,
        alias="neededUnits",
        ge=0,
    )

    city: str = "Unknown"

    is_urgent: bool = Field(
        default=False,
        alias="isUrgent",
    )

    service_type: str = Field(
        default="unknown",
        alias="serviceType",
    )

    status: Optional[DispatchStatus] = None

    distance_km: Optional[float] = Field(
        default=None,
        alias="distanceKm",
        ge=0,
    )

    urgency_score: Optional[float] = Field(
        default=None,
        alias="urgencyScore",
        ge=0,
        le=100,
    )

    blood_match_score: Optional[float] = Field(
        default=None,
        alias="bloodMatchScore",
        ge=0,
        le=100,
    )

    created_at: Optional[datetime] = Field(
        default=None,
        alias="createdAt",
    )

    updated_at: Optional[datetime] = Field(
        default=None,
        alias="updatedAt",
    )

    @computed_field
    @property
    def map_priority(self) -> str:
        """
        Frontend heat-zone priority.
        """

        if self.is_urgent:
            return "critical"

        if self.urgency_score and self.urgency_score >= 80:
            return "high"

        if self.urgency_score and self.urgency_score >= 50:
            return "medium"

        return "normal"


# =========================================================
# CANDIDATE DONOR / DRIVER DTO
# =========================================================


class CandidateDTO(GeoLocationSchema):
    """
    Donor / ambulance / driver candidate.
    """

    id: str

    full_name: Optional[str] = Field(
        default=None,
        alias="fullName",
    )

    blood_group: Optional[str] = Field(
        default=None,
        alias="bloodGroup",
    )

    is_available: bool = Field(
        default=True,
        alias="isAvailable",
    )

    active_score: float = Field(
        default=0.0,
        alias="activeScore",
        ge=0,
        le=100,
    )

    distance_km: Optional[float] = Field(
        default=None,
        alias="distanceKm",
        ge=0,
    )

    eta_minutes: Optional[int] = Field(
        default=None,
        alias="etaMinutes",
        ge=0,
    )

    vehicle_type: Optional[str] = Field(
        default=None,
        alias="vehicleType",
    )

    service_type: Optional[str] = Field(
        default=None,
        alias="serviceType",
    )


# =========================================================
# ASSIGNMENT RESULT DTO
# =========================================================


class AssignmentResultDTO(DispatchBaseSchema):
    """
    Uber-style assignment response.
    """

    assigned: bool

    request_id: str = Field(
        ...,
        alias="requestId",
    )

    donor_id: Optional[str] = Field(
        default=None,
        alias="donorId",
    )

    score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    eta_minutes: Optional[int] = Field(
        default=None,
        alias="etaMinutes",
        ge=0,
    )

    reason: Optional[str] = None

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# =========================================================
# LIVE LOCATION STREAM DTO
# =========================================================


class LocationUpdateDTO(GeoLocationSchema):
    """
    Real-time websocket location payload.
    """

    user_id: str = Field(
        ...,
        alias="userId",
    )

    service_type: str = Field(
        ...,
        alias="serviceType",
    )

    is_active: bool = Field(
        default=True,
        alias="isActive",
    )

    speed_kmh: Optional[float] = Field(
        default=None,
        alias="speedKmh",
        ge=0,
    )

    heading: Optional[float] = Field(
        default=None,
        ge=0,
        le=360,
    )

    accuracy_meters: Optional[float] = Field(
        default=None,
        alias="accuracyMeters",
        ge=0,
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# =========================================================
# REQUEST EVENT DTO
# =========================================================


class DispatchEventDTO(DispatchBaseSchema):
    """
    Enterprise event stream payload.
    """

    event: DispatchEventType

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    data: Dict[str, Any]


# =========================================================
# MAP CLUSTER DTO
# =========================================================


class MapClusterDTO(GeoLocationSchema):
    """
    Uber heat-zone style cluster.
    """

    cluster_id: str = Field(
        ...,
        alias="clusterId",
    )

    count: int = Field(
        ...,
        ge=0,
    )

    urgent_count: int = Field(
        default=0,
        alias="urgentCount",
        ge=0,
    )

    service_types: List[str] = Field(
        default_factory=list,
        alias="serviceTypes",
    )

    items: List[NearbyRequestDTO] = Field(
        default_factory=list,
    )

    @computed_field
    @property
    def heat_level(self) -> str:
        """
        Frontend map intensity indicator.
        """

        if self.count >= 100:
            return "extreme"

        if self.count >= 50:
            return "high"

        if self.count >= 20:
            return "medium"

        return "low"


# =========================================================
# WEBSOCKET MESSAGE WRAPPER
# =========================================================


class WebSocketDispatchEnvelope(DispatchBaseSchema):
    """
    Standardized websocket envelope.

    Prevents protocol inconsistency.
    """

    type: str

    payload: Dict[str, Any]

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    correlation_id: Optional[str] = Field(
        default=None,
        alias="correlationId",
    )


# =========================================================
# AUDIT RESPONSE DTO
# =========================================================


class DispatchAuditDTO(DispatchBaseSchema):
    """
    Internal-safe audit payload.
    """

    request_id: Optional[str] = Field(
        default=None,
        alias="requestId",
    )

    actor_id: Optional[str] = Field(
        default=None,
        alias="actorId",
    )

    operation: str

    status: str

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    ) 