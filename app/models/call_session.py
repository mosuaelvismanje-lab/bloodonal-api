import enum
from datetime import datetime
from typing import Optional, Any, List

from sqlalchemy import (
    String,
    DateTime,
    Enum as SAEnum,
    JSON,
    func,
    Integer  # ✅ Added missing import
)
# Modern SQLAlchemy 2.0 Mapped types
from sqlalchemy.orm import Mapped, mapped_column

# Import the shared Base from your central database config
from app.database import Base


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

    # ✅ id now uses the imported Integer type
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)

    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    room_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    caller_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    callee_ids: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    callee_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    call_mode: Mapped[CallMode] = mapped_column(
        SAEnum(CallMode, native_enum=False),
        nullable=False,
        default=CallMode.VOICE
    )

    status: Mapped[CallStatus] = mapped_column(
        SAEnum(CallStatus, native_enum=False),
        nullable=False,
        default=CallStatus.PENDING
    )

    token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=True
    )

    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    session_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<CallSession(id={self.id}, session_id={self.session_id}, status={self.status})>"
