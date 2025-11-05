# app/models/transport_request.py
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.database import Base

class TransportRequest(Base):
    __tablename__ = "transport_requests"
    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    pickup_latitude = Column(Float, nullable=False)
    pickup_longitude = Column(Float, nullable=False)
    dropoff_latitude = Column(Float, nullable=False)
    dropoff_longitude = Column(Float, nullable=False)
    details = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
