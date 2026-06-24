# =========================================================
# FILE: app/schemas/user/preference_response.py
# =========================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    ConfigDict,
    computed_field,
)

from app.schemas.base import BaseSchema


class PreferenceResponse(BaseSchema):
    """
    =========================================================
    USER PREFERENCE RESPONSE DTO
    =========================================================
    Frontend-safe settings response.
    =========================================================
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    # =====================================================
    # IDS
    # =====================================================
    id: UUID

    user_id: UUID

    # =====================================================
    # APP EXPERIENCE
    # =====================================================
    language: Optional[str] = "en"

    timezone: Optional[str] = "UTC"

    theme: Optional[str] = "system"

    # =====================================================
    # NOTIFICATIONS
    # =====================================================
    push_notifications_enabled: bool = True

    sms_notifications_enabled: bool = False

    email_notifications_enabled: bool = True

    marketing_notifications_enabled: bool = False

    emergency_alerts_enabled: bool = True

    # =====================================================
    # PRIVACY
    # =====================================================
    profile_visibility: Optional[str] = "public"

    show_online_status: bool = True

    show_last_seen: bool = True

    allow_location_tracking: bool = True

    # =====================================================
    # ACCESSIBILITY
    # =====================================================
    large_text_enabled: bool = False

    reduced_motion_enabled: bool = False

    high_contrast_enabled: bool = False

    # =====================================================
    # AUDIT
    # =====================================================
    created_at: datetime

    updated_at: Optional[datetime] = None

    # =====================================================
    # COMPUTED FIELDS
    # =====================================================
    @computed_field
    @property
    def notifications_enabled(self) -> bool:
        """
        Aggregate notification state.
        """

        return any([
            self.push_notifications_enabled,
            self.sms_notifications_enabled,
            self.email_notifications_enabled,
        ])

    @computed_field
    @property
    def accessibility_enabled(self) -> bool:
        """
        Aggregate accessibility state.
        """

        return any([
            self.large_text_enabled,
            self.reduced_motion_enabled,
            self.high_contrast_enabled,
        ])