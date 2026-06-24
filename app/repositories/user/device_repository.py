from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from fastapi import HTTPException, status

from app.models.user.user_device import UserDevice

logger = logging.getLogger(__name__)


class DeviceRepositoryError(Exception):
    pass


class DeviceRepository:
    """
    =========================================================
    DEVICE REPOSITORY (ENTERPRISE FINAL)
    =========================================================

    Handles:
    - device registration
    - multi-device tracking
    - last active updates
    - device deactivation
    - soft delete support
    =========================================================
    """

    # =====================================================
    # REGISTER / UPSERT DEVICE
    # =====================================================
    async def register_device(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        device_id: str,
        platform: str,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> UserDevice:
        try:
            now = datetime.now(timezone.utc)

            existing = await self.get_by_device_id(db, device_id=device_id)

            if existing:
                existing.platform = platform
                existing.device_model = device_model
                existing.app_version = app_version
                existing.ip_address = ip_address
                existing.is_active = True
                existing.last_active_at = now
                existing.updated_at = now

                await db.commit()
                await db.refresh(existing)
                return existing

            device = UserDevice(
                user_id=user_id,
                device_id=device_id,
                platform=platform,
                device_model=device_model,
                app_version=app_version,
                ip_address=ip_address,
                is_active=True,
                created_at=now,
                updated_at=now,
                last_active_at=now,
            )

            db.add(device)
            await db.commit()
            await db.refresh(device)

            return device

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Device registration failed")
            raise DeviceRepositoryError("Failed to register device") from exc

    # =====================================================
    # GET DEVICE BY ID
    # =====================================================
    async def get_by_device_id(
        self,
        db: AsyncSession,
        *,
        device_id: str,
    ) -> Optional[UserDevice]:
        stmt = select(UserDevice).where(
            and_(
                UserDevice.device_id == device_id,
                UserDevice.is_active.is_(True),
            )
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =====================================================
    # USER DEVICES
    # =====================================================
    async def get_user_devices(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> List[UserDevice]:
        stmt = select(UserDevice).where(
            UserDevice.user_id == user_id
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # =====================================================
    # TOUCH DEVICE (LAST ACTIVE)
    # =====================================================
    async def touch_device(
        self,
        db: AsyncSession,
        *,
        device_id: str,
        ip_address: Optional[str] = None,
    ) -> UserDevice:
        try:
            device = await self.get_by_device_id(db, device_id=device_id)

            if not device:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Device not found",
                )

            device.last_active_at = datetime.now(timezone.utc)
            device.updated_at = datetime.now(timezone.utc)

            if ip_address:
                device.ip_address = ip_address

            await db.commit()
            await db.refresh(device)

            return device

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Device touch failed")
            raise DeviceRepositoryError("Failed to update device") from exc

    # =====================================================
    # DEACTIVATE DEVICE
    # =====================================================
    async def deactivate_device(
        self,
        db: AsyncSession,
        *,
        device_id: str,
    ) -> bool:
        try:
            device = await self.get_by_device_id(db, device_id=device_id)

            if not device:
                return False

            device.is_active = False
            device.updated_at = datetime.now(timezone.utc)

            await db.commit()
            return True

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Device deactivation failed")
            raise DeviceRepositoryError("Failed to deactivate device") from exc


device_repository = DeviceRepository()