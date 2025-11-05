# app/models/blood_request.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from app.database import Base

class BloodRequest(Base):
    __tablename__ = "blood_requests"
    id = Column(Integer, primary_key=True, index=True)
    requester_name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    needed_units = Column(Integer, nullable=True)
    phone = Column(String, nullable=False)
    blood_type = Column(String(5), nullable=False)
    hospital = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    urgent = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
