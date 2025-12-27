import enum
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Enum as SAEnum, JSON, func
)
# 1. Use the modern DeclarativeBase import
from sqlalchemy.orm import DeclarativeBase


# 2. Modern SQLAlchemy 2.0 Base class
class Base(DeclarativeBase):
    pass


class CallMode(str, enum.Enum):
    VOICE = "voice"
    VIDEO = "video"


class CallStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ENDED = "ended"
    MISSED = "missed"
    CANCELLED = "cancelled"


class CallSession(Base):
    __tablename__ = "call_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False)
    room_name = Column(String(255), nullable=False, index=True)
    caller_id = Column(String(128), nullable=False, index=True)
    callee_ids = Column(JSON, nullable=True)
    callee_type = Column(String(64), nullable=True)

    # Using native_enum=False makes migrations easier across different DB types
    call_mode = Column(SAEnum(CallMode, native_enum=False), nullable=False, default=CallMode.VOICE)
    status = Column(SAEnum(CallStatus, native_enum=False), nullable=False, default=CallStatus.PENDING)

    token = Column(String(255), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # SUCCESS: You renamed this to session_metadata
    session_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)