from sqlalchemy import Column, Integer, String, DateTime, func
from app.database import Base


class TransportRequest(Base):
    __tablename__ = "transport_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)

    # --- pickup_latitude and pickup_longitude removed ---
    # --- dropoff_latitude and dropoff_longitude removed ---

    details = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())