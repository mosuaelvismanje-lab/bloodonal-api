# =========================================================
# FILE: app/mappers/user_mapper.py
# =========================================================

from __future__ import annotations

from typing import Optional, Any

from app.models.user.user import User
from app.models.user.user_profile import UserProfile

from app.schemas.user.profile_response import ProfileResponse
from app.schemas.user.user_response import UserResponse

from app.utils.geo_utils import safe_distance_km


class UserMapper:
    """
    =========================================================
    ENTERPRISE DTO MAPPER
    =========================================================

    Responsibilities:
    ---------------------------------------------------------
    - ORM → API DTO conversion
    - Sensitive field protection
    - Optional geo enrichment for location-based apps
    =========================================================
    """

    # =====================================================
    # USER RESPONSE
    # =====================================================
    @staticmethod
    def to_user_response(user: User) -> UserResponse:
        return UserResponse(
            id=str(user.id),
            email=user.email,
            phone=user.phone,
            username=user.username,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    # =====================================================
    # PROFILE RESPONSE
    # =====================================================
    @staticmethod
    def to_profile_response(
        profile: Optional[UserProfile],
    ) -> Optional[ProfileResponse]:

        if not profile:
            return None

        return ProfileResponse(
            id=str(profile.id),
            first_name=profile.first_name,
            last_name=profile.last_name,
            avatar_url=profile.avatar_url,
            gender=profile.gender,
            bio=profile.bio,
            date_of_birth=profile.date_of_birth,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    # =====================================================
    # GEO-ENRICHED USER RESPONSE (NEW)
    # =====================================================
    @staticmethod
    def to_geo_user_response(
        user: User,
        *,
        current_lat: float,
        current_lon: float,
    ) -> dict[str, Any]:
        """
        Returns user + distance from current location.

        Used for:
        - nearby users
        - driver matching
        - service discovery
        """

        distance_km = None

        # Safe extraction (depends on your model structure)
        user_lat = getattr(user, "latitude", None)
        user_lon = getattr(user, "longitude", None)

        if user_lat is not None and user_lon is not None:
            distance_km = safe_distance_km(
                current_lat,
                current_lon,
                user_lat,
                user_lon,
            )

        return {
            "id": str(user.id),
            "username": user.username,
            "is_active": user.is_active,
            "latitude": user_lat,
            "longitude": user_lon,
            "distance_km": distance_km,
        }


# =========================================================
# SINGLETON
# =========================================================
user_mapper = UserMapper()