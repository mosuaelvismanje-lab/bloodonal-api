from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserMedia(Base):
    """
    =========================================================
    USER MEDIA MODEL
    =========================================================

    Purpose:
    - User profile images
    - Medical documents
    - Verification documents
    - Emergency attachments
    - Identity/KYC uploads
    - Chat & support media
    - Cloud storage tracking

    Enterprise Features:
    - Cloud-ready architecture
    - CDN support
    - Secure file validation
    - Soft delete
    - Storage analytics
    - Upload lifecycle tracking
    """

    __tablename__ = "user_media"

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
    # FILE INFORMATION
    # =====================================================

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    original_file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    file_hash: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    # =====================================================
    # STORAGE PATHS
    # =====================================================

    storage_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="local",
        server_default=text("'local'"),
        index=True,
    )

    storage_bucket: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    public_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    cdn_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    thumbnail_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # MEDIA CLASSIFICATION
    # =====================================================

    media_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="image",
        server_default=text("'image'"),
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="profile",
        server_default=text("'profile'"),
        index=True,
    )

    visibility: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="private",
        server_default=text("'private'"),
        index=True,
    )

    # =====================================================
    # IMAGE / VIDEO METADATA
    # =====================================================

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # =====================================================
    # BUSINESS FLAGS
    # =====================================================

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    is_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    is_encrypted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    is_processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # =====================================================
    # ACCESS & SECURITY
    # =====================================================

    access_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # =====================================================
    # EXTRA METADATA
    # =====================================================

    alt_text: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    upload_source: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    device_info: Mapped[str | None] = mapped_column(
        String(255),
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
    )

    # =====================================================
    # SOFT DELETE
    # =====================================================

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # INDEXES + CONSTRAINTS
    # =====================================================

    __table_args__ = (
        # =================================================
        # PERFORMANCE INDEXES
        # =================================================
        Index(
            "idx_user_media_user_category",
            "user_id",
            "category",
        ),
        Index(
            "idx_user_media_media_type",
            "media_type",
        ),
        Index(
            "idx_user_media_visibility",
            "visibility",
        ),
        Index(
            "idx_user_media_primary",
            "user_id",
            "is_primary",
        ),
        Index(
            "idx_user_media_created",
            "created_at",
        ),

        # =================================================
        # VALIDATION CONSTRAINTS
        # =================================================
        CheckConstraint(
            "file_size_bytes >= 0",
            name="ck_user_media_file_size_positive",
        ),
        CheckConstraint(
            "width IS NULL OR width >= 0",
            name="ck_user_media_width_positive",
        ),
        CheckConstraint(
            "height IS NULL OR height >= 0",
            name="ck_user_media_height_positive",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_user_media_duration_positive",
        ),
        CheckConstraint(
            "access_count >= 0",
            name="ck_user_media_access_count_positive",
        ),
        CheckConstraint(
            "visibility IN ('public', 'private', 'restricted')",
            name="ck_user_media_visibility_valid",
        ),
        CheckConstraint(
            "media_type IN "
            "('image', 'video', 'audio', 'document', 'archive')",
            name="ck_user_media_type_valid",
        ),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserMedia("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"media_type={self.media_type}, "
            f"category={self.category}"
            f")>"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def is_image(self) -> bool:
        return self.media_type == "image"

    @property
    def is_video(self) -> bool:
        return self.media_type == "video"

    @property
    def is_document(self) -> bool:
        return self.media_type == "document"

    @property
    def formatted_size(self) -> str:
        size = self.file_size_bytes

        if size < 1024:
            return f"{size} B"

        if size < 1024 * 1024:
            return f"{round(size / 1024, 2)} KB"

        if size < 1024 * 1024 * 1024:
            return f"{round(size / (1024 * 1024), 2)} MB"

        return f"{round(size / (1024 * 1024 * 1024), 2)} GB"

    @property
    def has_thumbnail(self) -> bool:
        return bool(self.thumbnail_url)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False

        return datetime.utcnow() > self.expires_at.replace(tzinfo=None)

    def increment_access(self) -> None:
        self.access_count += 1
        self.last_accessed_at = datetime.utcnow()