from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserSession(Base):
    """
    =========================================================
    USER SESSION MODEL (ENTERPRISE AUTH LAYER)
    =========================================================

    Purpose:
    - Track user login sessions across devices
    - Support multi-device authentication
    - Enable secure logout / session revocation
    - Detect suspicious activity
    - Manage refresh token lifecycle

    This is NOT DB session.
    This is USER AUTH SESSION.
    =========================================================
    """

    __tablename__ = "user_sessions"

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
    # SESSION IDENTIFIERS
    # =====================================================

    session_token_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )

    refresh_token_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # =====================================================
    # DEVICE CONTEXT
    # =====================================================

    device_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    device_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    device_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )  # android, ios, web

    user_agent: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    platform: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # =====================================================
    # NETWORK CONTEXT
    # =====================================================

    ip_address: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    location: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    country: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # =====================================================
    # SESSION STATE
    # =====================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    revoke_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # =====================================================
    # SECURITY FLAGS
    # =====================================================

    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    risk_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # =====================================================
    # TOKEN LIFECYCLE
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    last_active_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # LOGIN METADATA
    # =====================================================

    login_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="password",
        server_default="password",
    )

    login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # =====================================================
    # SOFT DELETE
    # =====================================================

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # INDEXES
    # =====================================================

    __table_args__ = (
        Index("idx_session_user_active", "user_id", "is_active"),
        Index("idx_session_user_device", "user_id", "device_id"),
        Index("idx_session_token", "session_token_id"),
        Index("idx_session_ip", "ip_address"),
        Index("idx_session_expires", "expires_at"),
        Index("idx_session_revoked", "is_revoked"),
    )

    # =====================================================
    # METHODS
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserSession(user_id={self.user_id}, "
            f"device={self.device_type}, "
            f"active={self.is_active})>"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    def revoke(self, reason: str = "manual_logout") -> None:
        self.is_active = False
        self.is_revoked = True
        self.revoke_reason = reason
        self.revoked_at = datetime.utcnow()

    def touch(self) -> None:
        """Update last activity timestamp"""
        self.last_active_at = datetime.utcnow()

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    def extend_session(self, minutes: int = 60 * 24 * 7) -> None:
        """Extend session validity"""
        self.expires_at = datetime.utcnow() + timedelta(minutes=minutes)