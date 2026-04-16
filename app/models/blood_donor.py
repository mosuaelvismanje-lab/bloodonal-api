from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base


class BloodDonor(Base):
    """
    SQLAlchemy model representing a Blood Donor.
    Updated to support 'UNKNOWN' blood groups for inclusive registration.
    """
    __tablename__ = "blood_donors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=False, unique=True)

    # --- UPDATED: Added default and server_default for UNKNOWN ---
    # This ensures that if a user doesn't select a type, the DB
    # records it as "UNKNOWN" instead of crashing or being null.
    blood_type = Column(
        String(20),
        nullable=False,
        default="UNKNOWN",
        server_default="UNKNOWN"
    )

    city = Column(String(100), nullable=False)
    hospital = Column(String(100), nullable=True)

    # Status and Messaging
    is_active = Column(Boolean, default=True, nullable=False)
    fcm_token = Column(String, nullable=True)

    # Timestamps
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
            f"city={self.city!r})>"
        )
