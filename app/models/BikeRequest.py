from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, JSON
from app.database import Base


class BikeRequest(Base):
    """
    SQLAlchemy model representing a bike/taxi ride request.
    This tracks the service itself, whereas the Payment model tracks the money.
    """
    __tablename__ = "bike_requests"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ Ownership: Firebase UID
    user_id = Column(String, index=True, nullable=False)

    # ✅ Linking to your General Payment Model
    # We store the reference to link this request to the financial transaction
    payment_reference = Column(String, unique=True, nullable=True, index=True)

    # Request Details
    pickup_location = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=False)

    # Service Specifics
    bike_type = Column(String(50), default="standard")  # standard, delivery, premium
    is_free_tier = Column(Boolean, default=False)

    # ✅ Status Lifecycle: PENDING, ACTIVE, COMPLETED, CANCELLED
    status = Column(String(20), default="PENDING", nullable=False, index=True)

    # Flexibility for ride data (e.g. driver_id, estimated_time)
    metadata_json = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())   