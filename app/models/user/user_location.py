from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# =========================================================
# LOCATION SOURCE
# =========================================================


class LocationSource(str, Enum):
    GPS = "gps"
    NETWORK = "network"
    MANUAL = "manual"
    WEBSOCKET = "websocket"
    BACKGROUND = "background"


# =========================================================
# LOCATION STATUS
# =========================================================


class LocationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    IDLE = "IDLE"
    EMERGENCY = "EMERGENCY"
    HIDDEN = "HIDDEN"


# =========================================================
# LIVE LOCATION TABLE
# =========================================================


class UserLocation(Base):
    """
    =========================================================
    ENTERPRISE LIVE LOCATION MODEL
    =========================================================

    Features:
    - Real-time GPS tracking
    - Driver / donor / ambulance live map
    - Websocket sync support
    - Enterprise auditing
    - Geospatial-ready
    - Uber-style dispatch architecture

    Optimized for:
    - Fast nearest-user queries
    - Frequent updates
    - High concurrency
    """

    __tablename__ = "locations"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # =====================================================
    # USER / ENTITY REFERENCES
    # =====================================================

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    tracking_session_id: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    # =====================================================
    # SERVICE
    # =====================================================

    service_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # =====================================================
    # GEO LOCATION
    # =====================================================

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
    )

    altitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    # =====================================================
    # MOVEMENT DATA
    # =====================================================

    speed_kmh: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    heading: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    bearing: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    accuracy_meters: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    distance_travelled_km: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0",
    )

    # =====================================================
    # LIVE STATUS
    # =====================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    is_online: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    is_emergency: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    status: Mapped[LocationStatus] = mapped_column(
        SqlEnum(LocationStatus),
        nullable=False,
        default=LocationStatus.ACTIVE,
        index=True,
    )

    # =====================================================
    # TRACKING SOURCE
    # =====================================================

    source: Mapped[LocationSource] = mapped_column(
        SqlEnum(LocationSource),
        nullable=False,
        default=LocationSource.GPS,
    )

    device_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    device_model: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    network_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    battery_level: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # ADDRESS CACHE
    # =====================================================

    country: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    state: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    city: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    street: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    postal_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    formatted_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # GEOFENCE / ZONE
    # =====================================================

    zone_id: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    geofence_id: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )

    # =====================================================
    # SOCKET / LIVE STREAM
    # =====================================================

    websocket_channel: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    socket_id: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    # =====================================================
    # AUDIT
    # =====================================================

    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    tracked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    last_moved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # =====================================================
    # INDEXES
    # =====================================================

    __table_args__ = (
        Index(
            "idx_locations_geo",
            "latitude",
            "longitude",
        ),
        Index(
            "idx_locations_user_active",
            "user_id",
            "is_active",
        ),
        Index(
            "idx_locations_service_status",
            "service_type",
            "status",
        ),
        Index(
            "idx_locations_tracking_time",
            "tracked_at",
        ),
        Index(
            "idx_locations_service_geo",
            "service_type",
            "latitude",
            "longitude",
        ),
        Index(
            "idx_locations_emergency",
            "is_emergency",
            "service_type",
        ),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<Location("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"service_type={self.service_type}, "
            f"lat={self.latitude}, "
            f"lng={self.longitude}"
            f")>"
        )