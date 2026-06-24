from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException, status

from app.models.user.user_location import UserLocation  # your address model

logger = logging.getLogger(__name__)


class AddressRepositoryError(Exception):
    pass


class AddressRepository:
    """
    =========================================================
    ADDRESS / LOCATION REPOSITORY
    =========================================================

    Handles:
    - user addresses
    - location updates
    - default address management
    - soft delete support
    =========================================================
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
    ) -> UserLocation:
        try:
            now = datetime.now(timezone.utc)

            if is_default:
                await self._unset_default(db, user_id=user_id)

            address = UserLocation(
                user_id=user_id,
                label=label,
                address_line=address_line,
                city=city,
                country=country,
                latitude=latitude,
                longitude=longitude,
                is_default=is_default,
                created_at=now,
                updated_at=now,
            )

            db.add(address)
            await db.commit()
            await db.refresh(address)

            return address

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Address creation failed")
            raise AddressRepositoryError("Failed to create address") from exc

    # =====================================================
    # GET BY ID
    # =====================================================
    async def get_by_id(
        self,
        db: AsyncSession,
        *,
        address_id: str,
    ) -> Optional[UserLocation]:
        stmt = select(UserLocation).where(
            and_(
                UserLocation.id == address_id,
                UserLocation.is_deleted.is_(False) if hasattr(UserLocation, "is_deleted") else True,
            )
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =====================================================
    # GET USER ADDRESSES
    # =====================================================
    async def get_user_addresses(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> List[UserLocation]:
        stmt = select(UserLocation).where(
            UserLocation.user_id == user_id
        )

        if hasattr(UserLocation, "is_deleted"):
            stmt = stmt.where(UserLocation.is_deleted.is_(False))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # =====================================================
    # UPDATE ADDRESS
    # =====================================================
    async def update_address(
        self,
        db: AsyncSession,
        *,
        address_id: str,
        **updates,
    ) -> UserLocation:
        try:
            address = await self.get_by_id(db, address_id=address_id)

            if not address:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Address not found",
                )

            for key, value in updates.items():
                if hasattr(address, key) and value is not None:
                    setattr(address, key, value)

            address.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(address)

            return address

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Address update failed")
            raise AddressRepositoryError("Failed to update address") from exc

    # =====================================================
    # SET DEFAULT ADDRESS
    # =====================================================
    async def set_default(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        address_id: str,
    ) -> UserLocation:
        try:
            await self._unset_default(db, user_id=user_id)

            address = await self.get_by_id(db, address_id=address_id)

            if not address:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Address not found",
                )

            address.is_default = True
            address.updated_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(address)

            return address

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Set default address failed")
            raise AddressRepositoryError("Failed to set default address") from exc

    # =====================================================
    # DELETE ADDRESS (SOFT)
    # =====================================================
    async def delete_address(
        self,
        db: AsyncSession,
        *,
        address_id: str,
    ) -> bool:
        try:
            address = await self.get_by_id(db, address_id=address_id)

            if not address:
                return False

            if hasattr(address, "is_deleted"):
                address.is_deleted = True

            address.updated_at = datetime.now(timezone.utc)

            await db.commit()
            return True

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Address deletion failed")
            raise AddressRepositoryError("Failed to delete address") from exc

    # =====================================================
    # INTERNAL: UNSET DEFAULT
    # =====================================================
    async def _unset_default(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> None:
        stmt = select(UserLocation).where(
            and_(
                UserLocation.user_id == user_id,
                UserLocation.is_default.is_(True),
            )
        )

        result = await db.execute(stmt)
        current = result.scalar_one_or_none()

        if current:
            current.is_default = False
            current.updated_at = datetime.now(timezone.utc)


address_repository = AddressRepository()