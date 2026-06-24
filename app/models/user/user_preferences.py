from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserPreferences(Base):
    """
    =========================================================
    USER PREFERENCES MODEL
    =========================================================

    Purpose:
    - User personalization
    - Notification preferences
    - UI/UX customization
    - Privacy controls
    - Accessibility support
    - Language & localization
    - Realtime behavior settings

    Enterprise Features:
    - Fully scalable
    - JSON extensibility
    - Privacy-safe defaults
    - Analytics-ready
    - Feature-flag compatible
    """

    __tablename__ = "user_preferences"

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
        unique=True,
        index=True,
    )

    # =====================================================
    # LOCALIZATION
    # =====================================================

    language: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="en",
        server_default=text("'en'"),
    )

    timezone: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="UTC",
        server_default=text("'UTC'"),
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="USD",
        server_default=text("'USD'"),
    )

    date_format: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="YYYY-MM-DD",
        server_default=text("'YYYY-MM-DD'"),
    )

    time_format_24h: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # =====================================================
    # THEME & UI
    # =====================================================

    theme: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="system",
        server_default=text("'system'"),
    )

    accent_color: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    font_scale: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default=text("100"),
    )

    animations_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    compact_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    push_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    sms_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    emergency_alerts_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    marketing_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    sound_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    vibration_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # =====================================================
    # PRIVACY SETTINGS
    # =====================================================

    location_sharing_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    online_status_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    profile_visibility: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="public",
        server_default=text("'public'"),
    )

    activity_tracking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    analytics_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # =====================================================
    # ACCESSIBILITY
    # =====================================================

    accessibility_mode_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    screen_reader_support: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    high_contrast_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    reduce_motion_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    # =====================================================
    # REALTIME & TRACKING
    # =====================================================

    live_tracking_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    background_location_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    auto_refresh_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    # =====================================================
    # FEATURE FLAGS / CUSTOM SETTINGS
    # =====================================================

    experimental_features_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    custom_settings: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
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
    # TABLE CONFIGURATION
    # =====================================================

    __table_args__ = (
        # =================================================
        # PERFORMANCE INDEXES
        # =================================================
        Index(
            "idx_user_preferences_language",
            "language",
        ),
        Index(
            "idx_user_preferences_theme",
            "theme",
        ),
        Index(
            "idx_user_preferences_visibility",
            "profile_visibility",
        ),

        # =================================================
        # VALIDATION RULES
        # =================================================
        CheckConstraint(
            "font_scale >= 50 AND font_scale <= 300",
            name="ck_user_preferences_font_scale_valid",
        ),
        CheckConstraint(
            "theme IN ('light', 'dark', 'system')",
            name="ck_user_preferences_theme_valid",
        ),
        CheckConstraint(
            "profile_visibility IN ('public', 'private', 'contacts_only')",
            name="ck_user_preferences_visibility_valid",
        ),
    )

    # =====================================================
    # REPRESENTATION
    # =====================================================

    def __repr__(self) -> str:
        return (
            f"<UserPreferences("
            f"user_id={self.user_id}, "
            f"language={self.language}, "
            f"theme={self.theme}"
            f")>"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def is_dark_mode(self) -> bool:
        return self.theme == "dark"

    @property
    def notifications_enabled(self) -> bool:
        return any([
            self.push_notifications_enabled,
            self.sms_notifications_enabled,
            self.email_notifications_enabled,
        ])

    @property
    def accessibility_enabled(self) -> bool:
        return any([
            self.accessibility_mode_enabled,
            self.screen_reader_support,
            self.high_contrast_enabled,
            self.reduce_motion_enabled,
        ])

    def enable_all_notifications(self) -> None:
        self.push_notifications_enabled = True
        self.sms_notifications_enabled = True
        self.email_notifications_enabled = True

    def disable_all_notifications(self) -> None:
        self.push_notifications_enabled = False
        self.sms_notifications_enabled = False
        self.email_notifications_enabled = False