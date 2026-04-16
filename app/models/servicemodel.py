import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class ServiceUser(Base):
    """Unified table for all actors (Donors, Drivers, Nurses, Patients)."""
    __tablename__ = "service_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    city = Column(String, nullable=False)
    profile_image = Column(Text, nullable=True)

    # Track their activity
    listings = relationship("ServiceRequest", back_populates="owner")


class ServiceRequest(Base):
    """
    MODULAR 2026 CORE: One table for every service.
    Specific data (Blood Group, Car Type, Lab Type) goes into the 'details' JSON.
    """
    __tablename__ = "service_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("service_users.id"), nullable=False)

    # Core Identity
    service_type = Column(String, nullable=False, index=True)  # 'blood', 'taxi', 'lab', 'nurse'
    status = Column(String, default="pending", index=True)

    # General Info
    title = Column(String, nullable=False)
    location_city = Column(String, nullable=False, index=True)
    price_offered = Column(Float, default=0.0)

    # ✅ MODULAR WING: No more fixed columns for distance/quantity
    # Example for Blood: {"blood_group": "A+", "hospital": "General", "units": 2}
    # Example for Taxi: {"destination": "Molyko", "passengers": 3}
    details = Column(JSONB, nullable=False, server_default='{}')

    # Status & Payment
    is_paid = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ 48-HOUR EXPIRY: Crucial for the 2-day interval logic
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    owner = relationship("ServiceUser", back_populates="listings")

    def __repr__(self):
        return f"<ServiceRequest(id={self.id[:8]}, type={self.service_type}, city={self.location_city})>"

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at