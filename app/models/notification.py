# File: app/models/notification.py
from sqlalchemy import Column, String, Boolean, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
import uuid
from datetime import datetime

from app.database import Base

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, index=True, nullable=False)      # recipient user ID
    title = Column(String, nullable=True)                     # optional notification title
    sub_type = Column(String, nullable=False)                 # e.g., "incoming_call", "alert", etc.
    location = Column(String, nullable=False)                 # location info if needed
    phone = Column(String, nullable=False)                    # phone of sender/related contact
    message = Column(String, nullable=False)                  # main message content
    timestamp = Column(BigInteger, nullable=False)            # epoch millis
    read = Column(Boolean, default=False, nullable=False)     # read/unread status
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # creation timestamp

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, user_id={self.user_id}, "
            f"title={self.title}, sub_type={self.sub_type}, read={self.read})>"
        )
