# app/data/models.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class Usage(Base):
    __tablename__ = "usages"
    id = Column(String, primary_key=True)
    user_id = Column(String, index=True)
    service = Column(String, index=True)      # "doctor", "nurse", etc.
    paid = Column(Boolean, default=False)
    amount = Column(Integer, nullable=True)
    transaction_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
