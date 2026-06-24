# =========================================================
# FILE: app/services/address_service.py
# =========================================================

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user.address_repository import address_repository
from app.utils.geo_utils import haversine_distance_km, within_radius

logger = logging.getLogger(__name__)


class AddressServiceError(Exception):
    pass


class AddressService:
    """
    Enterprise Address Service
    """

    # =====================================================
    # CREATE ADDRESS
    # =====================================================
    async def create_address(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        label: Optional[str],
        address_line: str,
        city: str,
        country: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        is_default: bool = False,
    ) -> Any:
        try:
            return await address_repository.create_address(
                db,
                user_id=user_id,
                label=label,
                address_line=address_line,
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude,
                is_default=is_default,
            )

        except Exception as exc:
            logger.exception("Create address failed")
            raise AddressServiceError("Failed to create address") from exc

    # =====================================================
    # LIST ADDRESSES
    # =====================================================
    async def list_addresses(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> List[Any]:
        try:
            return await address_repository.get_user_addresses(
                db,
                user_id=user_id,
            )
        except Exception as exc:
            logger.exception("List addresses failed")
            raise AddressServiceError("Failed to list addresses") from exc

    # =====================================================
    # DISTANCE USING UTILS (IMPORTANT UPDATE)
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
        Uses centralized geo_utils (no duplicated math).
        """
        return haversine_distance_km(lat1, lon1, lat2, lon2)

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

        users = await address_repository.find_nearby_users(
            latitude=latitude,
            longitude=longitude,
            radius=radius_km,
        )

        results = []

        for user in users:
            if user.latitude is None or user.longitude is None:
                continue

            distance = self.calculate_distance_km(
                lat1=latitude,
                lon1=longitude,
                lat2=user.latitude,
                lon2=user.longitude,
            )

            if within_radius(latitude, longitude, user.latitude, user.longitude, radius_km):
                results.append(
                    {
                        "user_id": str(user.user_id),
                        "address_id": str(user.id),
                        "city": user.city,
                        "country": user.country,
                        "latitude": user.latitude,
                        "longitude": user.longitude,
                        "distance_km": round(distance, 2),
                    }
                )

        results.sort(key=lambda x: x["distance_km"])
        return results

    # =====================================================
    # UPDATE COORDINATES
    # =====================================================
    async def update_coordinates(
        self,
        *,
        address_id: UUID,
        latitude: float,
        longitude: float,
    ) -> Optional[Dict[str, Any]]:

        address = await address_repository.update_coordinates(
            address_id=address_id,
            latitude=latitude,
            longitude=longitude,
        )

        if not address:
            return None

        return {
            "id": str(address.id),
            "latitude": address.latitude,
            "longitude": address.longitude,
        }

    # =====================================================
    # SET PRIMARY
    # =====================================================
    async def set_primary_address(
        self,
        *,
        user_id: UUID,
        address_id: UUID,
    ) -> bool:
        return await address_repository.set_primary_address(
            user_id=user_id,
            address_id=address_id,
        )

    # =====================================================
    # DELETE
    # =====================================================
    async def delete_address(self, address_id: UUID) -> bool:
        return await address_repository.delete_address(address_id)