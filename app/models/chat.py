# app/models/chat.py

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Text, func
)
from sqlalchemy.orm import relationship
from app.database import Base

class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    id = Column(Integer, primary_key=True, index=True)
    # Tie a chat room to a specific blood_request/healthcare_request/etc:
    request_type  = Column(String, nullable=False)  # e.g. "blood_request"
    request_id    = Column(Integer, nullable=False) # e.g. blood_request.id

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    messages = relationship("Message", back_populates="room")


class Message(Base):
    __tablename__ = "messages"
    id         = Column(Integer, primary_key=True, index=True)
    room_id    = Column(Integer, ForeignKey("chat_rooms.id"), nullable=False)
    sender_id  = Column(Integer, nullable=False)  # your User.id (or donor/provider id)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    room = relationship("ChatRoom", back_populates="messages")
