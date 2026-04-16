from __future__ import annotations

from sqlalchemy import (
    Column, Integer, String, ForeignKey, DateTime, Text, func, Index
)
from sqlalchemy.orm import relationship
from app.database import Base


class ChatRoom(Base):
    """
    Orchestrates conversation sessions linked to specific modular requests.
    Supports Doctor Consults, Nurse visits, and Blood donation coordination.
    """
    __tablename__ = "chat_rooms"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ Link to the modular service type (blood, healthcare, taxi, bike)
    request_type = Column(String, nullable=False, index=True)
    request_id = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    messages = relationship(
        "Message",
        back_populates="room",
        cascade="all, delete-orphan",
        order_by="Message.created_at"  # Always fetch in chronological order
    )

    # Optimization: One room per unique request session
    __table_args__ = (
        Index("ix_chatroom_request_lookup", "request_type", "request_id", unique=True),
    )


class Message(Base):
    """
    Individual message entries within a ChatRoom.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False)

    # ✅ Changed: sender_id to String to support Firebase UIDs natively
    sender_id = Column(String, nullable=False, index=True)
    sender_type = Column(String, nullable=False)  # e.g., "patient", "provider", "admin"

    content = Column(Text, nullable=False)

    # ✅ Optimization: Index on created_at for fast 'load more' pagination
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    room = relationship("ChatRoom", back_populates="messages")