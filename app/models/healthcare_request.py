# app/models/healthcare_request.py
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.healthcare_provider import ProviderType  # import enum

class HealthcareRequest(Base):
    __tablename__ = "healthcare_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    city = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Link to a healthcare provider (doctor, nurse, or lab)
    assigned_provider_id = Column(Integer, ForeignKey("healthcare_providers.id"), nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship to access the provider directly
    provider = relationship("HealthcareProvider", backref="assigned_requests")

    # Optional helper property to check provider type easily
    @property
    def provider_type(self) -> ProviderType | None:
        if self.provider:
            return self.provider.service_type  # now uses enum
        return None
