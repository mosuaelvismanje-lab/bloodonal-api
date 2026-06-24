from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import MockUser

logger = logging.getLogger(__name__)


class AuthService:
    """
    Business logic layer for authentication module.
    Keeps router thin and reusable.
    """

    # =========================================================
    # SYNC USER LOGIC
    # =========================================================
    async def sync_user(
        self,
        db: AsyncSession,
        current_user: MockUser,
        *,
        platform: Optional[str] = None,
        device_id: Optional[str] = None,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
    ):
        from app.models.user import User  # lazy import

        query = select(User).where(User.auth_uid == str(current_user.auth_uid))
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if user is None:
            user = User(
                uid=current_user.uid,
                auth_uid=str(current_user.auth_uid),
                email=current_user.email.lower(),
                name=current_user.name,
                role=current_user.role,
                is_active=True,
                is_verified=False,
                auth_provider="firebase",
                created_at=now,
                updated_at=now,
                last_login_at=now,
            )
            db.add(user)
            created = True
        else:
            user.email = current_user.email.lower()
            user.name = current_user.name
            user.role = current_user.role
            user.updated_at = now
            user.last_login_at = now
            created = False

        await db.commit()
        await db.refresh(user)

        return {
            "user": user,
            "created": created,
            "updated_at": now,
        }

    # =========================================================
    # UPDATE FCM TOKEN
    # =========================================================
    async def update_fcm_token(
        self,
        db: AsyncSession,
        current_user: MockUser,
        token: str,
    ):
        from app.models.user import User

        query = select(User).where(User.auth_uid == str(current_user.auth_uid))
        result = await db.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return False

        user.fcm_token = token
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()
        return True

    # =========================================================
    # VALIDATE USER
    # =========================================================
    async def validate_user(self, current_user: MockUser) -> bool:
        return getattr(current_user, "is_active", True)

    # =========================================================
    # LOGOUT (NO DB REQUIRED)
    # =========================================================
    async def logout(self, current_user: MockUser) -> dict:
        logger.info("User logout: %s", current_user.uid)

        return {
            "success": True,
            "message": "Logout successful",
        }