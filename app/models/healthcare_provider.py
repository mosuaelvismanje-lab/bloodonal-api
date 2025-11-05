# app/models/healthcare_provider.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, func
from app.database import Base
import enum

# Define enum for provider type
class ProviderType(enum.Enum):
    doctor = "doctor"
    nurse = "nurse"
    lab = "lab"

class HealthcareProvider(Base):
    __tablename__ = "healthcare_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    service_type = Column(Enum(ProviderType), nullable=True)  # Use enum here
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
