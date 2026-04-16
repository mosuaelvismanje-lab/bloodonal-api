from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, func
from app.database import Base
import enum


# ✅ Expanded Enum for better real-world coverage
class ProviderType(str, enum.Enum):
    doctor = "doctor"
    nurse = "nurse"
    lab = "lab"
    ambulance = "ambulance"
    pharmacy = "pharmacy"
    clinic = "clinic"


class HealthcareProvider(Base):
    __tablename__ = "healthcare_providers"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ Added index=True to name for faster Autocomplete/Resolver searches
    name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False, index=True)

    # Using the Enum ensures data consistency in the database
    service_type = Column(Enum(ProviderType), nullable=True)

    # ✅ Added unique constraint to prevent duplicate registrations
    phone = Column(String, nullable=True, unique=True)
    email = Column(String, nullable=True, unique=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Note: Float columns for latitude and longitude have been removed
    # to maintain the 'Geo-Free' design and prioritize city-based matching.