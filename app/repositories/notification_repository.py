# =========================================================
# FILE: app/repositories/notification_repository.py
# =========================================================

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user.user_push_token import (
    UserPushToken,
)

from app.utils.datetime_utils import (
    is_expired,
    utc_now,
    utc_iso,
)

logger = logging.getLogger(__name__)


class NotificationRepositoryError(Exception):
    pass


class NotificationRepository:
    """
    =========================================================
    NOTIFICATION REPOSITORY
    =========================================================

    Responsibilities:
    ---------------------------------------------------------
    - FCM token registration
    - multi-device token storage
    - token lifecycle management
    - inactive token cleanup
    - push token analytics support
    =========================================================
    """

    # =====================================================
    # REGISTER TOKEN
    # =====================================================
    async def register_token(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        token: str,
        platform: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> UserPushToken:

        try:
            token = token.strip()

            existing = await self.get_by_token(
                db,
                token=token,
            )

            now = utc_now()

            # =============================================
            # UPDATE EXISTING TOKEN
            # =============================================
            if existing:
                existing.user_id = user_id
                existing.platform = platform
                existing.device_id = device_id
                existing.is_active = True
                existing.is_expired = False
                existing.last_used_at = now

                if hasattr(existing, "updated_at"):
                    existing.updated_at = now

                await db.commit()
                await db.refresh(existing)

                logger.info(
                    "[TOKEN_UPDATED] user=%s platform=%s",
                    user_id,
                    platform,
                )

                return existing

            # =============================================
            # CREATE NEW TOKEN
            # =============================================
            obj = UserPushToken(
                user_id=user_id,
                token=token,
                platform=platform,
                device_id=device_id,
                is_active=True,
                is_expired=False,
                created_at=now,
                updated_at=now if hasattr(UserPushToken, "updated_at") else None,
                last_used_at=now,
            )

            db.add(obj)

            await db.commit()
            await db.refresh(obj)

            logger.info(
                "[TOKEN_REGISTERED] user=%s platform=%s",
                user_id,
                platform,
            )

            return obj

        except SQLAlchemyError as exc:
            await db.rollback()

            logger.exception(
                "Token registration failed",
            )

            raise NotificationRepositoryError(
                "Failed to register token",
            ) from exc

    # =====================================================
    # GET TOKEN
    # =====================================================
    async def get_by_token(
        self,
        db: AsyncSession,
        *,
        token: str,
    ) -> Optional[UserPushToken]:

        stmt = select(UserPushToken).where(
            and_(
                UserPushToken.token == token,
                (
                    UserPushToken.is_deleted.is_(False)
                    if hasattr(UserPushToken, "is_deleted")
                    else True
                ),
            )
        )

        result = await db.execute(stmt)

        return result.scalar_one_or_none()

    # =====================================================
    # GET USER TOKENS
    # =====================================================
    async def get_user_tokens(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        active_only: bool = True,
    ) -> List[UserPushToken]:

        stmt = select(UserPushToken).where(
            UserPushToken.user_id == user_id,
        )

        if active_only:
            stmt = stmt.where(
                UserPushToken.is_active.is_(True),
            )

        if hasattr(UserPushToken, "is_deleted"):
            stmt = stmt.where(
                UserPushToken.is_deleted.is_(False),
            )

        result = await db.execute(stmt)

        return list(result.scalars().all())

    # =====================================================
    # GET ACTIVE TOKENS
    # =====================================================
    async def get_active_tokens(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> List[str]:

        tokens = await self.get_user_tokens(
            db,
            user_id=user_id,
            active_only=True,
        )

        return [
            t.token
            for t in tokens
            if (
                t.token
                and not getattr(t, "is_expired", False)
            )
        ]

    # =====================================================
    # TOUCH TOKEN
    # =====================================================
    async def touch_token(
        self,
        db: AsyncSession,
        *,
        token: str,
    ) -> bool:

        obj = await self.get_by_token(
            db,
            token=token,
        )

        if not obj:
            return False

        obj.last_used_at = utc_now()

        if hasattr(obj, "updated_at"):
            obj.updated_at = utc_now()

        await db.commit()

        return True

    # =====================================================
    # DEACTIVATE TOKEN
    # =====================================================
    async def deactivate_token(
        self,
        db: AsyncSession,
        *,
        token: str,
    ) -> bool:

        try:
            obj = await self.get_by_token(
                db,
                token=token,
            )

            if not obj:
                return False

            obj.is_active = False
            obj.is_expired = True
            obj.last_used_at = utc_now()

            if hasattr(obj, "updated_at"):
                obj.updated_at = utc_now()

            await db.commit()

            logger.info(
                "[TOKEN_DEACTIVATED] token=%s",
                token[:12],
            )

            return True

        except SQLAlchemyError as exc:
            await db.rollback()

            logger.exception(
                "Token deactivation failed",
            )

            raise NotificationRepositoryError(
                "Failed to deactivate token",
            ) from exc

    # =====================================================
    # DELETE TOKEN
    # =====================================================
    async def delete_token(
        self,
        db: AsyncSession,
        *,
        token: str,
    ) -> bool:

        try:
            obj = await self.get_by_token(
                db,
                token=token,
            )

            if not obj:
                return False

            # =============================================
            # SOFT DELETE
            # =============================================
            if hasattr(obj, "is_deleted"):
                obj.is_deleted = True

            obj.is_active = False
            obj.is_expired = True

            if hasattr(obj, "deleted_at"):
                obj.deleted_at = utc_now()

            if hasattr(obj, "updated_at"):
                obj.updated_at = utc_now()

            await db.commit()

            logger.info(
                "[TOKEN_DELETED] token=%s",
                token[:12],
            )

            return True

        except SQLAlchemyError as exc:
            await db.rollback()

            logger.exception(
                "Token delete failed",
            )

            raise NotificationRepositoryError(
                "Failed to delete token",
            ) from exc

    # =====================================================
    # CLEAR USER TOKENS
    # =====================================================
    async def clear_user_tokens(
        self,
        db: AsyncSession,
        *,
        user_id: str,
    ) -> int:

        try:
            tokens = await self.get_user_tokens(
                db,
                user_id=user_id,
                active_only=False,
            )

            count = 0
            now = utc_now()

            for token in tokens:
                token.is_active = False
                token.is_expired = True

                if hasattr(token, "updated_at"):
                    token.updated_at = now

                count += 1

            await db.commit()

            logger.info(
                "[USER_TOKENS_CLEARED] user=%s count=%s",
                user_id,
                count,
            )

            return count

        except SQLAlchemyError as exc:
            await db.rollback()

            logger.exception(
                "Clear user tokens failed",
            )

            raise NotificationRepositoryError(
                "Failed to clear tokens",
            ) from exc

    # =====================================================
    # CLEAN EXPIRED TOKENS
    # =====================================================
    async def cleanup_expired_tokens(
        self,
        db: AsyncSession,
    ) -> int:
        """
        Optional scheduled cleanup job.
        """

        try:
            stmt = select(UserPushToken)

            result = await db.execute(stmt)

            tokens = result.scalars().all()

            cleaned = 0

            for token in tokens:

                expires_at = getattr(
                    token,
                    "expires_at",
                    None,
                )

                if expires_at and is_expired(expires_at):

                    token.is_active = False
                    token.is_expired = True

                    if hasattr(token, "updated_at"):
                        token.updated_at = utc_now()

                    cleaned += 1

            await db.commit()

            logger.info(
                "[TOKEN_CLEANUP] cleaned=%s at=%s",
                cleaned,
                utc_iso(),
            )

            return cleaned

        except SQLAlchemyError as exc:
            await db.rollback()

            logger.exception(
                "Expired token cleanup failed",
            )

            raise NotificationRepositoryError(
                "Failed cleanup process",
            ) from exc

    # =====================================================
    # TOKEN STATS
    # =====================================================
    async def token_stats(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:

        stmt = select(UserPushToken)

        result = await db.execute(stmt)

        rows = list(result.scalars().all())

        total = len(rows)

        active = len([
            r for r in rows
            if getattr(r, "is_active", False)
        ])

        expired = len([
            r for r in rows
            if getattr(r, "is_expired", False)
        ])

        return {
            "total_tokens": total,
            "active_tokens": active,
            "expired_tokens": expired,
            "generated_at": utc_iso(),
        }


notification_repository = NotificationRepository()