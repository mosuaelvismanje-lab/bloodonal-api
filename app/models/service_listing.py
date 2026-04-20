import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base

class ServiceUser(Base):
    """
    Unified Profile Hub (2026).
    Acts as the central identity for Donors, Drivers, Nurses, and Patients.
    """
    __tablename__ = "service_users"
    # ✅ FIX: Prevents InvalidRequestError if the table is already in MetaData
    __table_args__ = {"extend_existing": True}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False, index=True)
    profile_image = Column(Text, nullable=True)

    # Relationship to their created requests
    listings = relationship(
        "ServiceListing",
        back_populates="owner",
        cascade="all, delete-orphan",
        foreign_keys="[ServiceListing.user_id]"
    )


class ServiceListing(Base):
    """
    POLYMORPHIC CORE: The single switchboard for all service requests.
    Handles Blood, Taxi, Nursing, and Consultations via JSONB 'details'.
    """
    __tablename__ = "service_listings"

    # Identity & Fulfillment
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("service_users.id"), nullable=False, index=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("service_users.id"), nullable=True, index=True)

    # Core Logic Switches
    service_type = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", server_default="PENDING", index=True)
    is_published = Column(Boolean, default=False, server_default="false", index=True)
    is_paid = Column(Boolean, default=False, server_default="false")
    activation_ref = Column(String, nullable=True, unique=True, index=True)

    # Data Payload
    title = Column(String, nullable=False)
    location_city = Column(String, nullable=False, index=True)
    price_offered = Column(Float, default=0.0)
    details = Column(JSONB, nullable=False, server_default='{}')

    # Timestamps & Expiry
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    owner = relationship("ServiceUser", foreign_keys=[user_id], back_populates="listings")
    provider = relationship("ServiceUser", foreign_keys=[provider_id])

    # ✅ Performance: Optimized Live Feed and Table Meta
    __table_args__ = (
        Index("ix_active_published_listings", "service_type", "is_published", "status"),
        {"extend_existing": True}
    )

    def __repr__(self):
        return f"<ServiceListing(id={str(self.id)[:8]}, type={self.service_type}, status={self.status})>"

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @staticmethod
    def calculate_default_expiry():
        return datetime.now(timezone.utc) + timedelta(days=2)