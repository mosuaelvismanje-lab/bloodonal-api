from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.core.constants.statuses import UserPresenceStatus


class UserPresence(Base):
    """
    =========================================================
    USER REALTIME PRESENCE MODEL
    =========================================================

    Purpose:
    - Track realtime online/offline state
    - Websocket connection visibility
    - Last activity monitoring
    - Dispatch/live tracking readiness
    - Realtime communication system

    Enterprise Features:
    - Multi-device support
    - Websocket aware
    - Heartbeat tracking
    - Last seen optimization
    - Presence analytics ready
    """

    __tablename__ = "user_presence"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        unique=True,
    )

    # =====================================================
    # USER LINK
    # =====================================================

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # =====================================================
    # PRESENCE STATUS
    # =====================================================

    status: Mapped[UserPresenceStatus] = mapped_column(
        Enum(
            UserPresenceStatus,
            name="user_presence_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default=UserPresenceStatus.OFFLINE,
        server_default=text("'offline'"),
        index=True,
    )

    # =====================================================
    # REALTIME CONNECTION
    # =====================================================

    is_online: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    websocket_connected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    socket_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )

    connection_channel: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # =====================================================
    # DEVICE CONTEXT
    # =====================================================

    platform: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    device_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # =====================================================
    # ACTIVITY TRACKING
    # =====================================================

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # SESSION FLAGS
    # =====================================================

    is_tracking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    is_available_for_dispatch: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    # =====================================================
    # AUDIT
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # =====================================================
    # INDEXES
    # =====================================================

    __table_args__ = (
        Index("idx_presence_user_online", "user_id", "is_online"),
        Index("idx_presence_status", "status"),
        Index("idx_presence_dispatch", "is_available_for_dispatch"),
        Index("idx_presence_last_seen", "last_seen_at"),
        Index("idx_presence_activity", "last_activity_at"),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserPresence "
            f"user_id={self.user_id} "
            f"status={self.status} "
            f"online={self.is_online}>"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def is_active_now(self) -> bool:
        return self.is_online and self.websocket_connected

    def mark_online(self) -> None:
        self.is_online = True
        self.websocket_connected = True
        self.status = UserPresenceStatus.ONLINE
        self.last_seen_at = datetime.utcnow()
        self.last_activity_at = datetime.utcnow()

    def mark_offline(self) -> None:
        self.is_online = False
        self.websocket_connected = False
        self.status = UserPresenceStatus.OFFLINE
        self.last_seen_at = datetime.utcnow()

    def heartbeat(self) -> None:
        self.last_heartbeat_at = datetime.utcnow()
        self.last_activity_at = datetime.utcnow()