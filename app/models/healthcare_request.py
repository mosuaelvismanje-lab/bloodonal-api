from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
from typing import Optional

# Importing the enum from the other model
from app.models.healthcare_provider import ProviderType


class HealthcareRequest(Base):
    __tablename__ = "healthcare_requests"

    id = Column(Integer, primary_key=True, index=True)

    # Added index=True for faster lookups in admin dashboards
    requester_name = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=False)

    # city is now the primary search filter for geo-matching
    city = Column(String, nullable=False, index=True)

    description = Column(Text, nullable=True)

    # Foreign Key remains nullable=True.
    # This allows a request to exist as "Pending" before a provider is assigned.
    assigned_provider_id = Column(Integer, ForeignKey("healthcare_providers.id"), nullable=True)

    # Indexing status helps when filtering for "active" vs "completed" requests
    status = Column(String, default="pending", index=True)

    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ NEW: Tracks exactly when the status changed to 'assigned'
    assigned_at = Column(DateTime(timezone=True), nullable=True)

    # ✅ NEW: Automatically updates every time the row is modified
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationship Update: Using 'lazy="selectin"' for Async compatibility.
    # This ensures that 'request.provider' is available without needing a
    # separate manual 'await' call in your routers.
    provider = relationship(
        "HealthcareProvider",
        backref="assigned_requests",
        lazy="selectin"
    )

    # Helper property to check provider type easily
    @property
    def provider_type(self) -> Optional[ProviderType]:
        if self.provider:
            return self.provider.service_type
        return None