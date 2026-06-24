# =========================================================
# FILE: app/models/user/user_address.py
# =========================================================

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class UserAddress(Base):
    """
    =========================================================
    USER ADDRESS MODEL
    =========================================================

    Enterprise Features
    ---------------------------------------------------------
    - Multi-address support
    - Primary/default address
    - GPS coordinates
    - Geo queries
    - Dispatch compatibility
    - Audit timestamps
    - Soft enterprise indexing
    =========================================================
    """

    __tablename__ = "user_addresses"

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
    # RELATIONSHIP
    # =====================================================
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # ADDRESS INFO
    # =====================================================
    label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Home",
    )

    address_line: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    apartment: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    landmark: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    city: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    state: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    postal_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    country: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    # =====================================================
    # GEO LOCATION
    # =====================================================
    latitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        index=True,
    )

    longitude: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        index=True,
    )

    # =====================================================
    # FLAGS
    # =====================================================
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================
    user = relationship(
        "User",
        back_populates="addresses",
        lazy="selectin",
    )

    # =====================================================
    # INDEXES
    # =====================================================
    __table_args__ = (
        Index(
            "idx_user_address_geo",
            "latitude",
            "longitude",
        ),
        Index(
            "idx_user_primary_address",
            "user_id",
            "is_primary",
        ),
    )

    # =====================================================
    # SERIALIZER
    # =====================================================
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "label": self.label,
            "address_line": self.address_line,
            "apartment": self.apartment,
            "landmark": self.landmark,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "is_primary": self.is_primary,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }

    # =====================================================
    # REPR
    # =====================================================
    def __repr__(self) -> str:
        return (
            f"UserAddress("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"city={self.city}, "
            f"country={self.country}"
            f")"
        )