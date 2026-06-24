from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserLocationHistory(Base):
    """
    =========================================================
    USER LOCATION HISTORY MODEL
    =========================================================

    Purpose:
    - Historical GPS tracking
    - Emergency movement replay
    - Driver / donor route analytics
    - Security & fraud investigations
    - Heatmaps and mobility insights

    Enterprise Ready:
    - Optimized indexes
    - Soft delete support
    - Geo metadata
    - Accuracy tracking
    - Battery-aware logging
    - Compliance auditing
    """

    __tablename__ = "user_location_history"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        unique=True,
    )

    # =====================================================
    # USER LINK
    # =====================================================

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # =====================================================
    # GEO COORDINATES
    # =====================================================

    latitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    longitude: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    altitude: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    accuracy_meters: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    heading: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    speed_kmh: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # =====================================================
    # LOCATION DETAILS
    # =====================================================

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    state: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    city: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    district: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    street: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    postal_code: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    formatted_address: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # =====================================================
    # TRACKING SOURCE
    # =====================================================

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="gps",
        server_default=text("'gps'"),
        index=True,
    )

    provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    tracking_session_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # =====================================================
    # DEVICE CONTEXT
    # =====================================================

    battery_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    is_mock_location: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    network_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    platform: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # =====================================================
    # BUSINESS FLAGS
    # =====================================================

    is_emergency_tracking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    is_background_tracking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================

    tracked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # =====================================================
    # SOFT DELETE
    # =====================================================

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # INDEXES + CONSTRAINTS
    # =====================================================

    __table_args__ = (
        Index(
            "idx_location_history_user_time",
            "user_id",
            "tracked_at",
        ),
        Index(
            "idx_location_history_geo",
            "latitude",
            "longitude",
        ),
        Index(
            "idx_location_history_city",
            "city",
            "tracked_at",
        ),
        Index(
            "idx_location_history_emergency",
            "is_emergency_tracking",
            "tracked_at",
        ),
        Index(
            "idx_location_history_tracking_session",
            "tracking_session_id",
            "tracked_at",
        ),
        CheckConstraint(
            "latitude >= -90 AND latitude <= 90",
            name="ck_location_history_latitude_valid",
        ),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_location_history_longitude_valid",
        ),
        CheckConstraint(
            "accuracy_meters IS NULL OR accuracy_meters >= 0",
            name="ck_location_history_accuracy_positive",
        ),
        CheckConstraint(
            "speed_kmh IS NULL OR speed_kmh >= 0",
            name="ck_location_history_speed_positive",
        ),
        CheckConstraint(
            "battery_level IS NULL OR "
            "(battery_level >= 0 AND battery_level <= 100)",
            name="ck_location_history_battery_valid",
        ),
        CheckConstraint(
            "heading IS NULL OR "
            "(heading >= 0 AND heading <= 360)",
            name="ck_location_history_heading_valid",
        ),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserLocationHistory("
            f"user_id={self.user_id}, "
            f"lat={self.latitude}, "
            f"lng={self.longitude}, "
            f"tracked_at={self.tracked_at}"
            f")>"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def coordinates(self) -> tuple[float, float]:
        return self.latitude, self.longitude

    @property
    def has_valid_accuracy(self) -> bool:
        return (
            self.accuracy_meters is not None
            and self.accuracy_meters <= 100
        )

    @property
    def is_high_speed(self) -> bool:
        return (
            self.speed_kmh is not None
            and self.speed_kmh >= 100
        )

    @property
    def full_location(self) -> str:
        parts = [
            self.street,
            self.city,
            self.state,
            self.country,
        ]
        return ", ".join(part for part in parts if part)