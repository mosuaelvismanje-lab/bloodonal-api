import uuid
import enum
from datetime import datetime, timezone
from typing import Optional, List, Dict

from sqlalchemy import String, DateTime, Enum as SAEnum, JSON, func, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# --- Enums for strict state management ---

class CallMode(str, enum.Enum):
    VOICE = "voice"
    VIDEO = "video"


class CallStatus(str, enum.Enum):
    INITIATED = "initiated"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    MISSED = "missed"
    REJECTED = "rejected"
    FAILED = "failed"


# --- The Model ---

class CallSession(Base):
    """
    SQLAlchemy 2.0 Model.
    Combines UUID security with automated duration and billing metrics.
    """
    __tablename__ = "call_sessions"

    # 1. Identity & Security (UUID is best for 2026 APIs)
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Human-readable or Jitsi-compatible room name
    room_name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)

    # 2. Participants
    caller_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    callee_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    callee_type: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g., 'doctor', 'donor'

    # 3. Call Configuration
    call_mode: Mapped[CallMode] = mapped_column(
        SAEnum(CallMode, native_enum=False), default=CallMode.VIDEO, nullable=False
    )
    status: Mapped[CallStatus] = mapped_column(
        SAEnum(CallStatus, native_enum=False), default=CallStatus.INITIATED, nullable=False
    )

    # Secure token for Jitsi/WebRTC handshake
    token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # 4. Temporal Data (Precision timing)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 5. Metrics & Metadata
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    # Store dynamic data like browser info, IP, or app version
    session_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<CallSession(id={self.id}, caller={self.caller_id}, status={self.status})>"

    # --- Logic Helpers ---

    @property
    def is_active(self) -> bool:
        return self.status in [CallStatus.INITIATED, CallStatus.ONGOING]

    def finalize_call(self):
        """Sets the end time and calculates final duration for billing."""
        self.ended_at = datetime.now(timezone.utc)
        if self.started_at:
            delta = self.ended_at - self.started_at
            self.duration_seconds = int(delta.total_seconds())
        self.status = CallStatus.COMPLETED
