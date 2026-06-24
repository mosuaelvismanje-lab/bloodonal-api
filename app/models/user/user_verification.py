from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
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
from app.core.constants.statuses import VerificationStatus


class UserVerification(Base):
    """
    =========================================================
    USER VERIFICATION MODEL
    =========================================================

    Purpose:
    - Email verification
    - Phone verification
    - Identity/KYC verification
    - Medical credential verification
    - Trust & compliance system

    Enterprise Features:
    - Multi-step verification support
    - OTP verification
    - Admin approval workflow
    - KYC document tracking
    - Fraud prevention ready
    """

    __tablename__ = "user_verifications"

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
    # EMAIL VERIFICATION
    # =====================================================

    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    email_verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            name="email_verification_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        server_default=text("'unverified'"),
        index=True,
    )

    # =====================================================
    # PHONE VERIFICATION
    # =====================================================

    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    phone_verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            name="phone_verification_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        server_default=text("'unverified'"),
        index=True,
    )

    # =====================================================
    # IDENTITY / KYC
    # =====================================================

    identity_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    identity_verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            name="identity_verification_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        server_default=text("'unverified'"),
        index=True,
    )

    identity_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # DOCUMENTS
    # =====================================================

    document_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    document_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    document_front_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    document_back_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    selfie_image_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # MEDICAL / PROFESSIONAL VERIFICATION
    # =====================================================

    medical_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    medical_verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(
            VerificationStatus,
            name="medical_verification_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        server_default=text("'unverified'"),
    )

    medical_license_number: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    medical_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # OTP / SECURITY
    # =====================================================

    verification_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    verification_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    last_verification_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # ADMIN REVIEW
    # =====================================================

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    internal_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # GLOBAL FLAGS
    # =====================================================

    is_fully_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    verification_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
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
        Index("idx_verification_user", "user_id"),
        Index("idx_verification_email", "email_verified"),
        Index("idx_verification_phone", "phone_verified"),
        Index("idx_verification_identity", "identity_verified"),
        Index("idx_verification_medical", "medical_verified"),
        Index("idx_verification_full", "is_fully_verified"),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserVerification "
            f"user_id={self.user_id} "
            f"email_verified={self.email_verified} "
            f"identity_verified={self.identity_verified}>"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def has_verified_email(self) -> bool:
        return self.email_verified

    @property
    def has_verified_phone(self) -> bool:
        return self.phone_verified

    @property
    def has_verified_identity(self) -> bool:
        return self.identity_verified

    def mark_email_verified(self) -> None:
        self.email_verified = True
        self.email_verified_at = datetime.utcnow()
        self.email_verification_status = VerificationStatus.VERIFIED

    def mark_phone_verified(self) -> None:
        self.phone_verified = True
        self.phone_verified_at = datetime.utcnow()
        self.phone_verification_status = VerificationStatus.VERIFIED

    def mark_identity_verified(self) -> None:
        self.identity_verified = True
        self.identity_verified_at = datetime.utcnow()
        self.identity_verification_status = VerificationStatus.VERIFIED

    def increment_attempts(self) -> None:
        self.verification_attempts += 1
        self.last_verification_attempt_at = datetime.utcnow()