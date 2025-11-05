# File: app/models/notification.py
from sqlalchemy import Column, String, Boolean, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(String, index=True, nullable=False)
    sub_type   = Column(String, nullable=False)
    location   = Column(String, nullable=False)
    phone      = Column(String, nullable=False)
    message    = Column(String, nullable=False)
    timestamp  = Column(BigInteger, nullable=False)   # epoch millis
    read       = Column(Boolean, default=False, nullable=False)
