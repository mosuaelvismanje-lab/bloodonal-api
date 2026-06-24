# =========================================================
# FILE: app/repositories/location_repository.py
# =========================================================

from __future__ import annotations

import logging
import uuid
from typing import Optional, Sequence

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user.user_address import UserAddress

logger = logging.getLogger(__name__)


class LocationRepository:
    """
    =========================================================
    ENTERPRISE LOCATION REPOSITORY
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - User location persistence
    - Nearby user queries
    - Coordinate updates
    - Primary address management
    - Geo filtering
    =========================================================
    """

    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    # =====================================================
    # CREATE ADDRESS
    # =====================================================
    async def create_address(
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
    ) -> UserAddress:

        address = UserAddress(
            user_id=user_id,
            label=label,
            country=country,
            city=city,
            address_line=address_line,
            latitude=latitude,
            longitude=longitude,
            is_primary=is_primary,
        )

        self.db.add(address)

        await self.db.commit()
        await self.db.refresh(address)

        return address

    # =====================================================
    # GET USER ADDRESSES
    # =====================================================
    async def get_user_addresses(
        self,
        user_id: uuid.UUID,
    ) -> Sequence[UserAddress]:

        query = select(UserAddress).where(
            UserAddress.user_id == user_id
        )

        result = await self.db.execute(query)

        return result.scalars().all()

    # =====================================================
    # GET PRIMARY ADDRESS
    # =====================================================
    async def get_primary_address(
        self,
        user_id: uuid.UUID,
    ) -> Optional[UserAddress]:

        query = select(UserAddress).where(
            and_(
                UserAddress.user_id == user_id,
                UserAddress.is_primary.is_(True),
            )
        )

        result = await self.db.execute(query)

        return result.scalars().first()

    # =====================================================
    # UPDATE COORDINATES
    # =====================================================
    async def update_coordinates(
        self,
        *,
        address_id: uuid.UUID,
        latitude: float,
        longitude: float,
    ) -> Optional[UserAddress]:

        query = select(UserAddress).where(
            UserAddress.id == address_id
        )

        result = await self.db.execute(query)

        address = result.scalars().first()

        if not address:
            return None

        address.latitude = latitude
        address.longitude = longitude

        await self.db.commit()
        await self.db.refresh(address)

        return address

    # =====================================================
    # SET PRIMARY ADDRESS
    # =====================================================
    async def set_primary_address(
        self,
        *,
        user_id: uuid.UUID,
        address_id: uuid.UUID,
    ) -> bool:

        addresses = await self.get_user_addresses(user_id)

        for address in addresses:
            address.is_primary = (
                address.id == address_id
            )

        await self.db.commit()

        return True

    # =====================================================
    # DELETE ADDRESS
    # =====================================================
    async def delete_address(
        self,
        address_id: uuid.UUID,
    ) -> bool:

        query = select(UserAddress).where(
            UserAddress.id == address_id
        )

        result = await self.db.execute(query)

        address = result.scalars().first()

        if not address:
            return False

        await self.db.delete(address)
        await self.db.commit()

        return True

    # =====================================================
    # FIND NEARBY USERS
    # =====================================================
    async def find_nearby_users(
        self,
        *,
        latitude: float,
        longitude: float,
        radius: float = 20.0,
    ) -> Sequence[UserAddress]:
        """
        Simple geo filtering.

        NOTE:
        -----------------------------------------------------
        Production systems should use:
        - PostGIS
        - GeoAlchemy2
        - Elasticsearch geo queries
        - MongoDB geospatial indexes
        =====================================================
        """

        lat_delta = radius / 111
        lon_delta = radius / 111

        query = select(UserAddress).where(
            and_(
                UserAddress.latitude >= latitude - lat_delta,
                UserAddress.latitude <= latitude + lat_delta,
                UserAddress.longitude >= longitude - lon_delta,
                UserAddress.longitude <= longitude + lon_delta,
            )
        )

        result = await self.db.execute(query)

        return result.scalars().all()