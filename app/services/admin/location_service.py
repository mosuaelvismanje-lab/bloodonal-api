# =========================================================
# FILE: app/services/location_service.py
# =========================================================

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.location_repository import (
    LocationRepository,
)

from app.utils.geo_utils import (
    haversine_distance_km,
    normalize_coordinates,
    within_radius,
)

logger = logging.getLogger(__name__)


class LocationService:
    """
    =========================================================
    ENTERPRISE LOCATION SERVICE
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - Coordinate calculations
    - Nearby search
    - Address management
    - Geo validation
    - Distance calculations
    - Radius filtering
    =========================================================
    """

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db
        self.repo = LocationRepository(db)

    # =====================================================
    # CREATE ADDRESS
    # =====================================================
    async def create_user_address(
        self,
        *,
        user_id: uuid.UUID,
        label: str,
        country: str,
        city: str,
        address_line: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        is_primary: bool = False,
    ) -> Dict[str, Any]:

        # =================================================
        # NORMALIZE GEO
        # =================================================
        if (
            latitude is not None
            and longitude is not None
        ):
            latitude, longitude = normalize_coordinates(
                latitude,
                longitude,
            )

        address = await self.repo.create_address(
            user_id=user_id,
            label=label.strip(),
            country=country.strip(),
            city=city.strip(),
            address_line=address_line.strip(),
            latitude=latitude,
            longitude=longitude,
            is_primary=is_primary,
        )

        logger.info(
            "[ADDRESS_CREATED] user_id=%s address_id=%s",
            user_id,
            address.id,
        )

        return {
            "id": str(address.id),
            "country": address.country,
            "city": address.city,
            "address_line": address.address_line,
            "latitude": address.latitude,
            "longitude": address.longitude,
            "is_primary": address.is_primary,
        }

    # =====================================================
    # GET USER LOCATIONS
    # =====================================================
    async def get_user_locations(
        self,
        user_id: uuid.UUID,
    ) -> list[Dict[str, Any]]:

        addresses = await self.repo.get_user_addresses(
            user_id
        )

        return [
            {
                "id": str(a.id),
                "city": a.city,
                "country": a.country,
                "latitude": a.latitude,
                "longitude": a.longitude,
                "is_primary": a.is_primary,
            }
            for a in addresses
        ]

    # =====================================================
    # DISTANCE CALCULATOR
    # =====================================================
    def calculate_distance_km(
        self,
        *,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Enterprise standardized geo distance.
        """

        return haversine_distance_km(
            lat1,
            lon1,
            lat2,
            lon2,
        )

    # =====================================================
    # CHECK RADIUS
    # =====================================================
    def is_within_radius(
        self,
        *,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
        radius_km: float,
    ) -> bool:

        return within_radius(
            lat1,
            lon1,
            lat2,
            lon2,
            radius_km,
        )

    # =====================================================
    # FIND NEARBY USERS
    # =====================================================
    async def find_nearby_users(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_km: float = 20.0,
    ) -> list[Dict[str, Any]]:

        # =================================================
        # VALIDATE COORDINATES
        # =================================================
        latitude, longitude = normalize_coordinates(
            latitude,
            longitude,
        )

        users = await self.repo.find_nearby_users(
            latitude=latitude,
            longitude=longitude,
            radius=radius_km,
        )

        results = []

        for user in users:

            if (
                user.latitude is None
                or user.longitude is None
            ):
                continue

            try:
                user_lat, user_lon = normalize_coordinates(
                    user.latitude,
                    user.longitude,
                )

                distance = haversine_distance_km(
                    latitude,
                    longitude,
                    user_lat,
                    user_lon,
                )

                # =========================================
                # STRICT RADIUS FILTER
                # =========================================
                if not within_radius(
                    latitude,
                    longitude,
                    user_lat,
                    user_lon,
                    radius_km,
                ):
                    continue

                results.append(
                    {
                        "user_id": str(user.user_id),
                        "address_id": str(user.id),
                        "city": user.city,
                        "country": user.country,
                        "latitude": user_lat,
                        "longitude": user_lon,
                        "distance_km": distance,
                    }
                )

            except Exception as exc:
                logger.warning(
                    "[INVALID_USER_COORDINATE] user=%s error=%s",
                    getattr(user, "user_id", None),
                    exc,
                )

        results.sort(
            key=lambda x: x["distance_km"]
        )

        logger.info(
            "[NEARBY_USERS_FOUND] total=%s radius=%skm",
            len(results),
            radius_km,
        )

        return results

    # =====================================================
    # UPDATE COORDINATES
    # =====================================================
    async def update_coordinates(
        self,
        *,
        address_id: uuid.UUID,
        latitude: float,
        longitude: float,
    ) -> Optional[Dict[str, Any]]:

        latitude, longitude = normalize_coordinates(
            latitude,
            longitude,
        )

        address = await self.repo.update_coordinates(
            address_id=address_id,
            latitude=latitude,
            longitude=longitude,
        )

        if not address:
            return None

        logger.info(
            "[ADDRESS_COORDINATES_UPDATED] address_id=%s",
            address_id,
        )

        return {
            "id": str(address.id),
            "latitude": address.latitude,
            "longitude": address.longitude,
        }

    # =====================================================
    # SET PRIMARY ADDRESS
    # =====================================================
    async def set_primary_address(
        self,
        *,
        user_id: uuid.UUID,
        address_id: uuid.UUID,
    ) -> bool:

        success = await self.repo.set_primary_address(
            user_id=user_id,
            address_id=address_id,
        )

        if success:
            logger.info(
                "[PRIMARY_ADDRESS_UPDATED] user_id=%s address_id=%s",
                user_id,
                address_id,
            )

        return success

    # =====================================================
    # DELETE ADDRESS
    # =====================================================
    async def delete_address(
        self,
        address_id: uuid.UUID,
    ) -> bool:

        success = await self.repo.delete_address(
            address_id
        )

        if success:
            logger.info(
                "[ADDRESS_DELETED] address_id=%s",
                address_id,
            )

        return success

    # =====================================================
    # HEALTH CHECK
    # =====================================================
    async def health_check(
        self,
    ) -> Dict[str, Any]:

        return {
            "service": "location_service",
            "status": "healthy",
        }