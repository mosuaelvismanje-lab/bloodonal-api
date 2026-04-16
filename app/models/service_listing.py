import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class ServiceUser(Base):
    """
    Unified table for all actors (Donors, Drivers, Nurses, Patients).
    Acts as the Profile hub for the modular ecosystem.
    """
    __tablename__ = "service_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, index=True)  # 'donor', 'driver', 'patient'
    city = Column(String, nullable=False, index=True)
    profile_image = Column(Text, nullable=True)

    # Relationship to their created requests
    listings = relationship("ServiceListing", back_populates="owner", cascade="all, delete-orphan")


class ServiceListing(Base):
    """
    POLYMORPHIC CORE 2026: The single switchboard for all service requests.
    Merges ServiceRequest logic with Orchestrator activation state.
    """
    __tablename__ = "service_listings"

    # ✅ Security: UUID prevents ID scraping/enumeration
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Ownership & Fulfillment
    user_id = Column(UUID(as_uuid=True), ForeignKey("service_users.id"), nullable=False, index=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("service_users.id"), nullable=True, index=True)

    # Core Identity
    service_type = Column(String, nullable=False, index=True)  # 'blood-request', 'taxi-request'
    status = Column(String, default="PENDING", server_default="PENDING", index=True)

    # Orchestrator & Payment Switches
    is_published = Column(Boolean, default=False, server_default="false", index=True)
    is_paid = Column(Boolean, default=False, server_default="false")

    # ✅ Traceability: Links listing to the specific transaction/quota use
    activation_ref = Column(String, nullable=True, unique=True, index=True)

    # General Information
    title = Column(String, nullable=False)
    location_city = Column(String, nullable=False, index=True)
    price_offered = Column(Float, default=0.0)

    # ✅ Performance: JSONB allows for GIN indexing and fast nested queries
    # Example: details = {"blood_group": "B+", "hospital": "St. Johns"}
    details = Column(JSONB, nullable=False, server_default='{}')

    # Audit Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ✅ Expiry Logic: Essential for the 48-hour cleanup interval
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    owner = relationship("ServiceUser", foreign_keys=[user_id], back_populates="listings")
    provider = relationship("ServiceUser", foreign_keys=[provider_id])

    # ✅ Composite Index: Optimizes the 'Live Feed' (Published + Pending)
    __table_args__ = (
        Index("ix_active_published_listings", "service_type", "is_published", "status"),
    )

    def __repr__(self):
        return f"<ServiceListing(id={str(self.id)[:8]}, type={self.service_type}, status={self.status})>"

    @property
    def is_expired(self) -> bool:
        """Logic check for the application layer."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @staticmethod
    def calculate_default_expiry():
        """Standard helper for +2 days (48 hours)."""
        return datetime.now(timezone.utc) + timedelta(days=2)