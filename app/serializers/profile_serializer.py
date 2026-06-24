# =========================================================
# FILE: app/serializers/user/profile_serializer.py
# =========================================================

from __future__ import annotations

from typing import Any, Dict


class ProfileSerializer:
    """
    =========================================================
    PROFILE SERIALIZER (UPDATED ENTERPRISE + BLOOD SYSTEM)
    =========================================================
    """

    def to_response(self, profile: Any) -> Dict[str, Any]:
        return {
            # =================================================
            # CORE IDS
            # =================================================
            "id": str(profile.id),
            "user_id": str(profile.user_id),

            # =================================================
            # BASIC PROFILE
            # =================================================
            "first_name": getattr(profile, "first_name", None),
            "last_name": getattr(profile, "last_name", None),
            "full_name": getattr(profile, "full_name", None),
            "bio": getattr(profile, "bio", None),
            "gender": getattr(profile, "gender", None),

            # =================================================
            # CONTACT
            # =================================================
            "phone_number": getattr(profile, "phone_number", None),

            # =================================================
            # MEDIA
            # =================================================
            "avatar_url": getattr(profile, "avatar_url", None),
            "cover_photo_url": getattr(profile, "cover_photo_url", None),

            # =================================================
            # SOCIAL / WORK
            # =================================================
            "website": getattr(profile, "website", None),
            "company": getattr(profile, "company", None),
            "job_title": getattr(profile, "job_title", None),

            # =================================================
            # LOCATION (NEW)
            # =================================================
            "city": getattr(profile, "city", None),
            "state": getattr(profile, "state", None),
            "country": getattr(profile, "country", None),

            # =================================================
            # BLOOD SYSTEM (NEW)
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
            # EMERGENCY CONTACT (NEW)
            # =================================================
            "emergency_contact": getattr(profile, "emergency_contact", None),
            "emergency_name": getattr(profile, "emergency_name", None),
            "emergency_relationship": getattr(profile, "emergency_relationship", None),

            # =================================================
            # MEDICAL INFO (NEW)
            # =================================================
            "medical_notes": getattr(profile, "medical_notes", None),
            "allergies": getattr(profile, "allergies", None),
            "chronic_conditions": getattr(profile, "chronic_conditions", None),

            # =================================================
            # STATUS
            # =================================================
            "verified": getattr(profile, "verified", False),

            # =================================================
            # TIMESTAMPS
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


profile_serializer = ProfileSerializer()