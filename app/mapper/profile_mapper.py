# =========================================================
# FILE: app/mappers/profile_mapper.py
# =========================================================

from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.user.user_profile import UserProfile


class ProfileMapper:
    """
    =========================================================
    PROFILE MAPPER (ENTERPRISE + HEALTHCARE READY)
    =========================================================
    """

    # =====================================================
    # FULL PROFILE RESPONSE
    # =====================================================
    def to_response(
        self,
        profile: Optional[UserProfile],
    ) -> Optional[Dict[str, Any]]:

        if not profile:
            return None

        return {
            # =================================================
            # IDENTIFIERS
            # =================================================
            "id": str(profile.id),
            "user_id": str(profile.user_id),

            # =================================================
            # BASIC PROFILE
            # =================================================
            "full_name": getattr(profile, "full_name", None),
            "username": getattr(profile, "username", None),
            "bio": getattr(profile, "bio", None),
            "gender": getattr(profile, "gender", None),

            "avatar_url": getattr(profile, "avatar_url", None),
            "cover_photo_url": getattr(profile, "cover_photo_url", None),

            # =================================================
            # CONTACT
            # =================================================
            "phone_number": getattr(profile, "phone_number", None),

            # =================================================
            # LOCATION
            # =================================================
            "city": getattr(profile, "city", None),
            "state": getattr(profile, "state", None),
            "country": getattr(profile, "country", None),

            # =================================================
            # PERSONAL
            # =================================================
            "birth_date": (
                profile.birth_date.isoformat()
                if getattr(profile, "birth_date", None)
                else None
            ),

            # =================================================
            # BLOOD SYSTEM (CRITICAL)
            # =================================================
            "blood_group": getattr(profile, "blood_group", None),
            "is_donor": getattr(profile, "is_donor", False),
            "donation_count": getattr(profile, "donation_count", 0),
            "last_donation_at": (
                profile.last_donation_at.isoformat()
                if getattr(profile, "last_donation_at", None)
                else None
            ),

            # =================================================
            # EMERGENCY CONTACT
            # =================================================
            "emergency_contact": getattr(profile, "emergency_contact", None),
            "emergency_name": getattr(profile, "emergency_name", None),
            "emergency_relationship": getattr(profile, "emergency_relationship", None),

            # =================================================
            # SOCIAL / REPUTATION
            # =================================================
            "rating": getattr(profile, "rating", 0.0),
            "total_reviews": getattr(profile, "total_reviews", 0),

            # =================================================
            # STATUS
            # =================================================
            "verified": getattr(profile, "verified", False),
            "is_active": getattr(profile, "is_active", True),

            # =================================================
            # AUDIT
            # =================================================
            "created_at": (
                profile.created_at.isoformat()
                if getattr(profile, "created_at", None)
                else None
            ),
            "updated_at": (
                profile.updated_at.isoformat()
                if getattr(profile, "updated_at", None)
                else None
            ),
        }

    # =====================================================
    # COMPACT PROFILE (FOR LISTS / SEARCH / CHAT UI)
    # =====================================================
    def to_compact_response(
        self,
        profile: Optional[UserProfile],
    ) -> Optional[Dict[str, Any]]:

        if not profile:
            return None

        return {
            "id": str(profile.id),
            "user_id": str(profile.user_id),
            "full_name": getattr(profile, "full_name", None),
            "username": getattr(profile, "username", None),
            "avatar_url": getattr(profile, "avatar_url", None),
            "blood_group": getattr(profile, "blood_group", None),
            "is_donor": getattr(profile, "is_donor", False),
            "verified": getattr(profile, "verified", False),
        }


# =========================================================
# SINGLETON
# =========================================================
profile_mapper = ProfileMapper()