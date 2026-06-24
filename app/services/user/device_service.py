from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user.user_device import UserDevice


class DeviceService:
    """
    Device tracking + lifecycle management.
    """

    def _now(self):
        return datetime.now(timezone.utc)

    async def register_device(
        self,
        db: AsyncSession,
        *,
        user_id: uuid.UUID,
        device_id: str,
        platform: str,
        model: Optional[str] = None,
    ) -> UserDevice:

        stmt = select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.device_id == device_id,
        )

        result = await db.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            device.last_seen_at = self._now()
            device.is_active = True
        else:
            device = UserDevice(
                id=uuid.uuid4(),
                user_id=user_id,
                device_id=device_id,
                platform=platform,
                model=model,
                is_active=True,
                created_at=self._now(),
                last_seen_at=self._now(),
            )
            db.add(device)

        await db.commit()
        await db.refresh(device)
        return device

    async def deactivate_device(
        self,
        db: AsyncSession,
        device_id: str,
    ) -> None:
        stmt = select(UserDevice).where(UserDevice.device_id == device_id)
        result = await db.execute(stmt)
        device = result.scalar_one_or_none()

        if device:
            device.is_active = False
            await db.commit()


device_service = DeviceService()