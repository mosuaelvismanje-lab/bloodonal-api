from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.user.enums import DevicePlatform
from app.core.constants.statuses import DeviceStatus


class UserDevice(Base):
    """
    =========================================================
    USER DEVICE MODEL (FIXED 2026)
    =========================================================
    """

    __tablename__ = "user_devices"

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
    # USER RELATION
    # =====================================================

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # =====================================================
    # DEVICE IDENTIFICATION
    # =====================================================

    device_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    device_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    platform: Mapped[DevicePlatform] = mapped_column(
        Enum(
            DevicePlatform,
            name="device_platform_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        index=True,
    )

    operating_system: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # =====================================================
    # DEVICE SECURITY (FIXED ENUM HANDLING)
    # =====================================================

    status: Mapped[DeviceStatus] = mapped_column(
        Enum(
            DeviceStatus,
            name="device_status_enum",
            native_enum=True,
            create_constraint=True,
            values_callable=lambda obj: [e.value for e in obj],
        ),
        nullable=False,
        default=DeviceStatus.ACTIVE,
        server_default=text("'active'::text"),
        index=True,
    )

    is_trusted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    is_emulator: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    is_rooted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    # =====================================================
    # PUSH NOTIFICATIONS
    # =====================================================

    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)

    push_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # =====================================================
    # NETWORK
    # =====================================================

    ip_address: Mapped[str | None] = mapped_column(String(100), nullable=True)
    network_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # =====================================================
    # SESSION TRACKING (FIXED UTC HANDLING)
    # =====================================================

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    login_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    # =====================================================
    # METADATA
    # =====================================================

    device_fingerprint: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    )

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # =====================================================
    # CONSTRAINTS / INDEXES
    # =====================================================

    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_user_device"),

        Index("idx_device_user_status", "user_id", "status"),
        Index("idx_device_platform", "platform"),
        Index("idx_device_last_login", "last_login_at"),
        Index("idx_device_trusted", "is_trusted"),
        Index("idx_device_push", "push_enabled"),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserDevice user_id={self.user_id} "
            f"device_id={self.device_id} "
            f"platform={self.platform}>"
        )

    # =====================================================
    # HELPERS (FIXED UTC SAFE)
    # =====================================================

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return self.status == DeviceStatus.ACTIVE

    def mark_login(self) -> None:
        now = self._now()
        self.last_login_at = now
        self.last_seen_at = now
        self.login_count += 1

    def mark_seen(self) -> None:
        self.last_seen_at = self._now()

    def revoke(self) -> None:
        self.status = DeviceStatus.REVOKED
        self.revoked_at = self._now()

    def trust_device(self) -> None:
        self.is_trusted = True

    def untrust_device(self) -> None:
        self.is_trusted = False