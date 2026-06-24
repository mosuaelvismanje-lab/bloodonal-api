# =========================================================
# FILE: app/models/notification.py
# =========================================================

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.database import Base

from app.utils.datetime_utils import (
    utc_now,
    utc_iso,
)


class Notification(Base):
    """
    =========================================================
    ENTERPRISE NOTIFICATION MODEL
    =========================================================

    Handles:
    ---------------------------------------------------------
    - Push notifications
    - In-app notifications
    - Read/unread tracking
    - Delivery state
    - Deep-link payloads
    - Notification analytics correlation
    - Soft deletion support
    - Enterprise auditing
    =========================================================
    """

    __tablename__ = "notifications"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # =====================================================
    # USER RELATION
    # =====================================================
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.uid",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # CONTENT
    # =====================================================
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # =====================================================
    # CLASSIFICATION
    # =====================================================
    type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    priority: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="normal",
        index=True,
    )

    channel: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        default="push",
    )

    # =====================================================
    # PAYLOAD DATA
    # =====================================================
    data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # =====================================================
    # DELIVERY STATUS
    # =====================================================
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    delivered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    failed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # AUDIT / CORRELATION
    # =====================================================
    notification_id: Mapped[
        Optional[str]
    ] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    correlation_id: Mapped[
        Optional[str]
    ] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    external_message_id: Mapped[
        Optional[str]
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    source_service: Mapped[
        Optional[str]
    ] = mapped_column(
        String(120),
        nullable=True,
    )

    # =====================================================
    # DEEP LINKING
    # =====================================================
    action_url: Mapped[
        Optional[str]
    ] = mapped_column(
        Text,
        nullable=True,
    )

    image_url: Mapped[
        Optional[str]
    ] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # SOFT DELETE
    # =====================================================
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    deleted_at: Mapped[
        Optional[DateTime]
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================
    read_at: Mapped[
        Optional[DateTime]
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    delivered_at: Mapped[
        Optional[DateTime]
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================
    user = relationship(
        "User",
        back_populates="notifications",
        lazy="joined",
    )

    # =====================================================
    # INDEXES
    # =====================================================
    __table_args__ = (
        Index(
            "idx_notifications_user_read",
            "user_id",
            "is_read",
        ),
        Index(
            "idx_notifications_created_at",
            "created_at",
        ),
        Index(
            "idx_notifications_category",
            "category",
        ),
        Index(
            "idx_notifications_type",
            "type",
        ),
        Index(
            "idx_notifications_deleted",
            "is_deleted",
        ),
        Index(
            "idx_notifications_user_created",
            "user_id",
            "created_at",
        ),
    )

    # =====================================================
    # HELPERS
    # =====================================================
    def mark_as_read(
        self,
    ) -> None:
        self.is_read = True
        self.read_at = utc_now()
        self.updated_at = utc_now()

    def mark_as_unread(
        self,
    ) -> None:
        self.is_read = False
        self.read_at = None
        self.updated_at = utc_now()

    def mark_delivered(
        self,
        *,
        message_id: Optional[str] = None,
    ) -> None:
        self.delivered = True
        self.failed = False
        self.delivered_at = utc_now()

        if message_id:
            self.external_message_id = message_id

        self.updated_at = utc_now()

    def mark_failed(
        self,
    ) -> None:
        self.failed = True
        self.delivered = False
        self.updated_at = utc_now()

    def archive(
        self,
    ) -> None:
        self.archived = True
        self.updated_at = utc_now()

    def soft_delete(
        self,
    ) -> None:
        self.is_deleted = True
        self.deleted_at = utc_now()
        self.updated_at = utc_now()

    # =====================================================
    # SERIALIZER
    # =====================================================
    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "id": str(self.id),
            "user_id": str(self.user_id),

            "title": self.title,
            "body": self.body,

            "type": self.type,
            "category": self.category,
            "priority": self.priority,
            "channel": self.channel,

            "data": self.data,

            "is_read": self.is_read,
            "delivered": self.delivered,
            "failed": self.failed,
            "archived": self.archived,

            "notification_id": self.notification_id,
            "correlation_id": self.correlation_id,
            "external_message_id": self.external_message_id,
            "source_service": self.source_service,

            "action_url": self.action_url,
            "image_url": self.image_url,

            "is_deleted": self.is_deleted,

            "read_at": (
                self.read_at.isoformat()
                if self.read_at
                else None
            ),

            "delivered_at": (
                self.delivered_at.isoformat()
                if self.delivered_at
                else None
            ),

            "deleted_at": (
                self.deleted_at.isoformat()
                if self.deleted_at
                else None
            ),

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else utc_iso()
            ),

            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else utc_iso()
            ),
        }

    # =====================================================
    # REPR
    # =====================================================
    def __repr__(
        self,
    ) -> str:

        return (
            f"Notification("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"type={self.type}, "
            f"category={self.category}, "
            f"is_read={self.is_read}, "
            f"delivered={self.delivered}"
            f")"
        )