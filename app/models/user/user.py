from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class User(Base):
    """
    =========================================================
    PRODUCTION USER MODEL (2026 READY)
    =========================================================

    Primary key:
    - uid (UUID)

    Foreign keys in other tables must use:
    - ForeignKey("users.uid")
    """

    __tablename__ = "users"

    # =====================================================
    # PRIMARY IDENTIFIER
    # =====================================================

    uid: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )

    # =====================================================
    # AUTH SOURCE OF TRUTH
    # =====================================================

    auth_uid: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    # =====================================================
    # PROFILE
    # =====================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Unknown User",
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        index=True,
    )

    profile_image: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    bio: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # AUTH + SECURITY
    # =====================================================

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user",
        server_default="user",
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )

    auth_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="firebase",
        server_default="firebase",
    )

    # =====================================================
    # DEVICE / APP CONTEXT
    # =====================================================

    platform: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    device_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    device_model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    app_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # =====================================================
    # PUSH NOTIFICATIONS
    # =====================================================

    fcm_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        index=True,
    )

    notification_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # =====================================================
    # SESSION TRACKING
    # =====================================================

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_ip_address: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # =====================================================
    # AUDIT
    # =====================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def display_name(self) -> str:
        return self.name or self.email

    @property
    def is_staff(self) -> bool:
        return self.role.lower() in {"admin", "super_admin"}

    def mark_seen(self) -> None:
        self.last_seen_at = datetime.now(timezone.utc)

    def increment_login(self) -> None:
        self.login_count += 1
        self.last_login_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"<User(uid={self.uid}, "
            f"auth_uid={self.auth_uid}, "
            f"email={self.email}, "
            f"role={self.role})>"
        )