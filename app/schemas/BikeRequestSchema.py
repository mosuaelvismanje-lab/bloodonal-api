from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, JSON
from app.database import Base

class BikeRequest(Base):
    """
    SQLAlchemy model representing a bike/taxi ride service request.
    This tracks the logistics of the ride itself.
    """
    __tablename__ = "bike_requests"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ Ownership: Links to the Firebase User UID
    user_id = Column(String, index=True, nullable=False)

    # ✅ Cross-Reference: Links to the General Payment Model reference
    # This allows you to join the service request with the financial transaction
    payment_reference = Column(String, unique=True, nullable=True, index=True)

    # Location Details
    pickup_point = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=False)

    # Service Configuration
    # bike_type: standard, cargo (for deliveries), or executive
    bike_type = Column(String(50), default="standard", index=True)
    is_free_usage = Column(Boolean, default=False)

    # ✅ Request Lifecycle
    # Statuses: PENDING, SEARCHING, ACTIVE, COMPLETED, CANCELLED
    status = Column(String(20), default="PENDING", nullable=False, index=True)

    # Flexible metadata for 2026 features (e.g., driver_id, estimated_price)
    metadata_json = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<BikeRequest id={self.id} user={self.user_id} status={self.status}>"