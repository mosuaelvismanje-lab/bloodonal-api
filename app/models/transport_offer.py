# app/models/transport_offer.py
from sqlalchemy import Column, Integer, String, Float, DateTime, func
from app.database import Base

class TransportOffer(Base):
    __tablename__ = "transport_offers"
    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    available_latitude = Column(Float, nullable=False)
    available_longitude = Column(Float, nullable=False)
    capacity = Column(Integer, nullable=True)
    details = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
