# app/models/call_session.py
import enum
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Enum as SAEnum, JSON, Boolean, func
)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


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
    session_id = Column(String(64), unique=True, index=True, nullable=False)  # uuid4 hex
    room_name = Column(String(255), nullable=False, index=True)                # jitsi room name
    caller_id = Column(String(128), nullable=False, index=True)
    callee_ids = Column(JSON, nullable=True)   # list of callee ids
    callee_type = Column(String(64), nullable=True)  # e.g., "doctor", "driver"
    call_mode = Column(SAEnum(CallMode), nullable=False, default=CallMode.VOICE)
    token = Column(String(255), nullable=True)   # optional call token
    status = Column(SAEnum(CallStatus), nullable=False, default=CallStatus.PENDING)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
