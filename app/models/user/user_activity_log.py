from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class UserActivityLog(Base):
    """
    =========================================================
    USER ACTIVITY LOG
    =========================================================
    Enterprise Audit Trail
    =========================================================
    """

    __tablename__ = "user_activity_logs"

    # =====================================================
    # PRIMARY KEY
    # =====================================================

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    # =====================================================
    # USER
    # =====================================================

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # =====================================================
    # ACTIVITY
    # =====================================================

    action = Column(
        String(120),
        nullable=False,
        index=True,
    )

    category = Column(
        String(80),
        nullable=False,
        server_default=text("'general'"),
        default="general",
        index=True,
    )

    description = Column(
        Text,
        nullable=True,
    )

    # =====================================================
    # REQUEST CONTEXT
    # =====================================================

    ip_address = Column(
        String(100),
        nullable=True,
        index=True,
    )

    user_agent = Column(
        Text,
        nullable=True,
    )

    platform = Column(
        String(50),
        nullable=True,
    )

    device_id = Column(
        String(255),
        nullable=True,
        index=True,
    )

    app_version = Column(
        String(50),
        nullable=True,
    )

    # =====================================================
    # LOCATION
    # =====================================================

    country = Column(
        String(100),
        nullable=True,
        index=True,
    )

    city = Column(
        String(100),
        nullable=True,
        index=True,
    )

    latitude = Column(
        String(50),
        nullable=True,
    )

    longitude = Column(
        String(50),
        nullable=True,
    )

    # =====================================================
    # SECURITY
    # =====================================================

    success = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    severity = Column(
        String(30),
        nullable=False,
        default="info",
        server_default=text("'info'"),
        index=True,
    )

    is_suspicious = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    # =====================================================
    # ENTITY TRACKING
    # =====================================================

    entity_type = Column(
        String(100),
        nullable=True,
        index=True,
    )

    entity_id = Column(
        String(255),
        nullable=True,
        index=True,
    )

    # =====================================================
    # JSON METADATA
    # =====================================================

    metadata_json = Column(
        JSON,
        nullable=True,
    )

    # =====================================================
    # PERFORMANCE
    # =====================================================

    response_time_ms = Column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # TIMESTAMP
    # =====================================================

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # =====================================================
    # INDEXES
    # =====================================================

    __table_args__ = (
        Index(
            "idx_activity_user_created",
            "user_id",
            "created_at",
        ),
        Index(
            "idx_activity_action_created",
            "action",
            "created_at",
        ),
        Index(
            "idx_activity_category",
            "category",
        ),
        Index(
            "idx_activity_security",
            "is_suspicious",
            "severity",
        ),
        Index(
            "idx_activity_entity",
            "entity_type",
            "entity_id",
        ),
        Index(
            "idx_activity_ip",
            "ip_address",
        ),
        Index(
            "idx_activity_device",
            "device_id",
        ),
    )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def is_security_event(self) -> bool:
        return self.severity.lower() in {
            "warning",
            "critical",
            "security",
        }

    @property
    def location(self) -> str:
        if self.city and self.country:
            return f"{self.city}, {self.country}"

        return self.country or "Unknown"

    # =====================================================
    # REPR
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserActivityLog("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"action={self.action}, "
            f"severity={self.severity}"
            f")>"
        )