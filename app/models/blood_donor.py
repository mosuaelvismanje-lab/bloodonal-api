# app/models/blood_donor.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from app.database import Base

class BloodDonor(Base):
    __tablename__ = "blood_donors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False, unique=True)
    blood_type = Column(String, nullable=False)
    city = Column(String(100), nullable=False)
    hospital = Column(String(100), nullable=True)
    latitude    = Column(Float, nullable=True)
    longitude   = Column(Float, nullable=True)
    is_active   = Column(Boolean, default=True, nullable=False)
    fcm_token   = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    def __repr__(self):
        return (
            f"<BloodDonor(id={self.id!r}, name={self.name!r}, "
            f"phone={self.phone!r}, blood_type={self.blood_type!r}, "
            f"hospital={self.hospital!r})>"
        )

