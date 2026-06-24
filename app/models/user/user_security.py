from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class UserSecurity(Base):
    """
    =========================================================
    USER SECURITY MODEL
    =========================================================

    PURPOSE
    ---------------------------------------------------------
    Enterprise-grade user security state management.

    Handles:
    - account locking
    - failed login tracking
    - password reset state
    - MFA flags
    - suspicious activity
    - brute-force protection
    - compliance audit support
    - security hardening

    NOTES
    ---------------------------------------------------------
    - Firebase/Auth provider remains primary auth authority
    - This model stores INTERNAL SECURITY STATE
    - Designed for enterprise-scale systems
    =========================================================
    """

    __tablename__ = "user_security"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        unique=True,
    )

    # =====================================================
    # USER RELATION
    # =====================================================
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # =====================================================
    # ACCOUNT STATUS
    # =====================================================
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    is_locked = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    is_suspended = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    is_banned = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    # =====================================================
    # LOGIN SECURITY
    # =====================================================
    failed_login_attempts = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    successful_login_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_failed_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    lock_reason = Column(
        String(255),
        nullable=True,
    )

    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # =====================================================
    # PASSWORD / AUTH
    # =====================================================
    auth_provider = Column(
        String(50),
        nullable=False,
        default="firebase",
        server_default=text("'firebase'"),
        index=True,
    )

    password_changed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    password_reset_required = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # =====================================================
    # MFA / 2FA
    # =====================================================
    mfa_enabled = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    mfa_method = Column(
        String(50),
        nullable=True,
    )

    mfa_verified_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # DEVICE / NETWORK SECURITY
    # =====================================================
    last_ip_address = Column(
        String(100),
        nullable=True,
    )

    last_user_agent = Column(
        String(500),
        nullable=True,
    )

    trusted_device_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    suspicious_activity_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    last_suspicious_activity_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # SECURITY FLAGS
    # =====================================================
    requires_reverification = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    compromised = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    security_note = Column(
        String(500),
        nullable=True,
    )

    # =====================================================
    # AUDIT TIMESTAMPS
    # =====================================================
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # =====================================================
    # SOFT DELETE
    # =====================================================
    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # INDEXES + CONSTRAINTS
    # =====================================================
    __table_args__ = (
        # ================================
        # INDEXES
        # ================================
        Index("idx_security_user", "user_id"),
        Index("idx_security_locked", "is_locked", "locked_until"),
        Index("idx_security_banned", "is_banned"),
        Index("idx_security_compromised", "compromised"),
        Index("idx_security_mfa", "mfa_enabled"),
        Index("idx_security_active", "is_active", "is_deleted"),

        # ================================
        # DATA INTEGRITY
        # ================================
        CheckConstraint(
            "failed_login_attempts >= 0",
            name="ck_security_failed_login_non_negative",
        ),

        CheckConstraint(
            "successful_login_count >= 0",
            name="ck_security_success_login_non_negative",
        ),

        CheckConstraint(
            "trusted_device_count >= 0",
            name="ck_security_trusted_devices_non_negative",
        ),

        CheckConstraint(
            "suspicious_activity_count >= 0",
            name="ck_security_suspicious_non_negative",
        ),

        CheckConstraint(
            "(is_deleted = false AND deleted_at IS NULL) "
            "OR "
            "(is_deleted = true AND deleted_at IS NOT NULL)",
            name="ck_security_soft_delete_consistency",
        ),
    )

    # =====================================================
    # HELPERS
    # =====================================================
    def record_successful_login(self) -> None:
        self.successful_login_count += 1
        self.failed_login_attempts = 0
        self.last_login_at = datetime.utcnow()

    def record_failed_login(self) -> None:
        self.failed_login_attempts += 1
        self.last_failed_login_at = datetime.utcnow()

    def lock_account(
        self,
        reason: str,
        until: datetime | None = None,
    ) -> None:
        self.is_locked = True
        self.lock_reason = reason
        self.locked_until = until

    def unlock_account(self) -> None:
        self.is_locked = False
        self.lock_reason = None
        self.locked_until = None
        self.failed_login_attempts = 0

    def mark_compromised(self, note: str | None = None) -> None:
        self.compromised = True
        self.security_note = note

    def clear_compromised(self) -> None:
        self.compromised = False

    def enable_mfa(self, method: str) -> None:
        self.mfa_enabled = True
        self.mfa_method = method
        self.mfa_verified_at = datetime.utcnow()

    def disable_mfa(self) -> None:
        self.mfa_enabled = False
        self.mfa_method = None
        self.mfa_verified_at = None

    # =====================================================
    # DEBUG
    # =====================================================
    def __repr__(self) -> str:
        return (
            f"<UserSecurity "
            f"user_id={self.user_id} "
            f"locked={self.is_locked} "
            f"banned={self.is_banned} "
            f"mfa={self.mfa_enabled}>"
        )