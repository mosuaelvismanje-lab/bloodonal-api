from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    String,
    Boolean,
    ForeignKey,
    func,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class UserPushToken(Base):
    """
    =========================================================
    PUSH NOTIFICATION TOKEN STORAGE (FCM / APNS)
    =========================================================
    - Supports multiple devices per user
    - Used for real-time notifications
    - Compatible with Firebase Cloud Messaging
    =========================================================
    """

    __tablename__ = "user_push_tokens"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # =====================================================
    # USER LINK
    # =====================================================
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # =====================================================
    # DEVICE INFO
    # =====================================================
    token = Column(String(512), nullable=False, unique=True, index=True)

    platform = Column(String(50), nullable=True)  # android / ios / web

    device_id = Column(String(255), nullable=True)

    # =====================================================
    # STATUS
    # =====================================================
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")

    is_expired = Column(Boolean, nullable=False, default=False, server_default="false")

    # =====================================================
    # TIMESTAMP
    # =====================================================
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_used_at = Column(DateTime(timezone=True), nullable=True)

    # =====================================================
    # INDEXES
    # =====================================================
    __table_args__ = (
        Index("idx_push_user_active", "user_id", "is_active"),
        Index("idx_push_token_active", "token", "is_active"),
    )

    # =====================================================
    # HELPERS
    # =====================================================
    def mark_used(self) -> None:
        self.last_used_at = datetime.utcnow()

    def __repr__(self) -> str:
        return f"<UserPushToken user_id={self.user_id} platform={self.platform}>"