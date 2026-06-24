from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class ServiceListing(Base):
    """
    Core domain entity representing a service offered by a user.

    Activation targets:
    - Paid activation
    - Free quota activation
    - Admin override publishing
    - AI ranking and analytics
    """

    __tablename__ = "service_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user = relationship("User", backref="service_listings")

    service_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    fee: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    activation_ref: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def mark_published(self) -> None:
        self.is_published = True
        self.published_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def mark_unpublished(self) -> None:
        self.is_published = False
        self.published_at = None
        self.updated_at = datetime.now(timezone.utc)

    def attach_metadata(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            return

        current = self.metadata_json or {}
        current.update(data)
        self.metadata_json = current
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "service_type": self.service_type,
            "title": self.title,
            "description": self.description,
            "amount": float(self.amount) if self.amount is not None else None,
            "fee": float(self.fee) if self.fee is not None else None,
            "is_published": self.is_published,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "activation_ref": self.activation_ref,
            "idempotency_key": self.idempotency_key,
            "metadata_json": self.metadata_json,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<ServiceListing(id={self.id}, "
            f"service_type={self.service_type}, "
            f"published={self.is_published})>"
        )


Index(
    "ix_service_listing_user_service",
    ServiceListing.user_id,
    ServiceListing.service_type,
)

Index(
    "ix_service_listing_publish_state",
    ServiceListing.is_published,
    ServiceListing.created_at,
)

Index(
    "ix_service_listing_activation",
    ServiceListing.activation_ref,
)