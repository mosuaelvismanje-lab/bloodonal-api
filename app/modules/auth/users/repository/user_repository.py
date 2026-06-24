from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID, NAMESPACE_DNS, uuid5

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


class UserRepositoryError(Exception):
    pass


class UserRepository:
    """
    Production repository for user persistence.

    Aligns with:
    - Firebase auth sync
    - /auth/sync
    - /users/initialize
    - /auth/fcm-token
    - login tracking
    - audit-safe updates
    - soft delete support
    """

    # =========================================================
    # READ METHODS
    # =========================================================
    async def get_by_uid(
        self,
        db: AsyncSession,
        uid: UUID,
    ) -> Optional[User]:
        stmt = select(User).where(User.uid == uid)
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_auth_uid(
        self,
        db: AsyncSession,
        auth_uid: str,
    ) -> Optional[User]:
        normalized = self._normalize_auth_uid(auth_uid)
        stmt = select(User).where(User.auth_uid == normalized)
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(
        self,
        db: AsyncSession,
        email: str,
    ) -> Optional[User]:
        normalized = self._normalize_email(email)
        stmt = select(User).where(User.email == normalized)
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_auth_uid_or_email(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        email: str,
    ) -> Optional[User]:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        normalized_email = self._normalize_email(email)

        stmt = select(User).where(
            or_(
                User.auth_uid == normalized_auth_uid,
                User.email == normalized_email,
            )
        )
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================
    # UPSERT / SYNC
    # =========================================================
    async def upsert_from_firebase(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        email: str,
        name: str,
        role: str = "user",
        platform: Optional[str] = None,
        device_id: Optional[str] = None,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
        auth_provider: str = "firebase",
        is_active: bool = True,
        is_verified: bool = False,
    ) -> Tuple[User, bool]:
        """
        Creates or updates a user record from Firebase-authenticated data.

        Returns:
            (user, created)
        """
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        normalized_email = self._normalize_email(email)
        normalized_name = self._normalize_name(name)
        normalized_role = self._normalize_role(role)
        normalized_platform = self._normalize_optional_text(platform)
        normalized_device_id = self._normalize_optional_text(device_id)
        normalized_device_model = self._normalize_optional_text(device_model)
        normalized_app_version = self._normalize_optional_text(app_version)
        normalized_provider = self._normalize_role(auth_provider)

        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            created = False

            if user is None:
                user = await self.get_by_email(db, normalized_email)

            if user is None:
                created = True
                user = User(
                    uid=self._stable_uuid(normalized_auth_uid),
                    auth_uid=normalized_auth_uid,
                    email=normalized_email,
                    name=normalized_name,
                    role=normalized_role,
                    is_active=is_active,
                    is_verified=is_verified,
                    is_admin=normalized_role in {"admin", "super_admin"},
                    auth_provider=normalized_provider,
                    platform=normalized_platform,
                    device_id=normalized_device_id,
                    device_model=normalized_device_model,
                    app_version=normalized_app_version,
                    created_at=now,
                    updated_at=now,
                    last_login_at=now,
                    last_seen_at=now,
                    login_count=1,
                )
                db.add(user)
            else:
                user.auth_uid = normalized_auth_uid
                user.email = normalized_email
                user.name = normalized_name
                user.role = normalized_role
                user.is_active = is_active
                user.is_verified = is_verified
                user.is_admin = normalized_role in {"admin", "super_admin"}
                user.auth_provider = normalized_provider
                user.platform = normalized_platform
                user.device_id = normalized_device_id
                user.device_model = normalized_device_model
                user.app_version = normalized_app_version
                user.last_login_at = now
                user.last_seen_at = now
                user.login_count = (user.login_count or 0) + 1
                user.updated_at = now
                if hasattr(user, "deleted_at"):
                    user.deleted_at = None

            await db.commit()
            await db.refresh(user)
            return user, created

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to upsert user from Firebase")
            raise UserRepositoryError("Failed to synchronize user") from exc

    # =========================================================
    # INITIALIZE / BOOTSTRAP
    # =========================================================
    async def initialize_user(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        email: str,
        name: str,
        platform: Optional[str] = None,
        auth_provider: str = "firebase",
    ) -> Tuple[User, bool]:
        """
        Convenience wrapper for initial profile creation.
        """
        return await self.upsert_from_firebase(
            db,
            auth_uid=auth_uid,
            email=email,
            name=name,
            role="user",
            platform=platform,
            auth_provider=auth_provider,
            is_active=True,
            is_verified=False,
        )

    # =========================================================
    # FCM TOKEN
    # =========================================================
    async def update_fcm_token(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        fcm_token: str,
    ) -> User:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        normalized_token = self._normalize_required_text(fcm_token, "fcm_token")
        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user.fcm_token = normalized_token
            user.updated_at = now

            await db.commit()
            await db.refresh(user)
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to update FCM token")
            raise UserRepositoryError("Failed to update FCM token") from exc

    async def clear_fcm_token(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
    ) -> User:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user.fcm_token = None
            user.updated_at = now

            await db.commit()
            await db.refresh(user)
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to clear FCM token")
            raise UserRepositoryError("Failed to clear FCM token") from exc

    # =========================================================
    # SESSION / AUDIT
    # =========================================================
    async def mark_login(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        ip_address: Optional[str] = None,
        device_id: Optional[str] = None,
        device_model: Optional[str] = None,
        app_version: Optional[str] = None,
    ) -> User:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user.last_login_at = now
            user.last_seen_at = now
            user.login_count = (user.login_count or 0) + 1
            user.last_ip_address = self._normalize_optional_text(ip_address)
            user.device_id = self._normalize_optional_text(device_id)
            user.device_model = self._normalize_optional_text(device_model)
            user.app_version = self._normalize_optional_text(app_version)
            user.updated_at = now

            await db.commit()
            await db.refresh(user)
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to mark login")
            raise UserRepositoryError("Failed to mark login") from exc

    async def touch_last_seen(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
    ) -> User:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user.last_seen_at = now
            user.updated_at = now

            await db.commit()
            await db.refresh(user)
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to update last seen")
            raise UserRepositoryError("Failed to update last seen") from exc

    async def deactivate_user(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
    ) -> User:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user.is_active = False
            user.deleted_at = now
            user.updated_at = now

            await db.commit()
            await db.refresh(user)
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to deactivate user")
            raise UserRepositoryError("Failed to deactivate user") from exc

    async def reactivate_user(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
    ) -> User:
        normalized_auth_uid = self._normalize_auth_uid(auth_uid)
        now = self._now()

        try:
            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            user.is_active = True
            user.deleted_at = None
            user.updated_at = now

            await db.commit()
            await db.refresh(user)
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("Failed to reactivate user")
            raise UserRepositoryError("Failed to reactivate user") from exc

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================
    def _stable_uuid(self, raw_auth_uid: str) -> UUID:
        try:
            return UUID(raw_auth_uid)
        except Exception:
            return uuid5(NAMESPACE_DNS, f"bloodonal:{raw_auth_uid}")

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _normalize_auth_uid(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="auth_uid is required",
            )
        return normalized

    def _normalize_email(self, value: str) -> str:
        normalized = (value or "").strip().lower()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="email is required",
            )
        return normalized

    def _normalize_name(self, value: str) -> str:
        normalized = (value or "").strip()
        return normalized if normalized else "Unknown User"

    def _normalize_role(self, value: str) -> str:
        normalized = (value or "user").strip().lower()
        return normalized if normalized else "user"

    def _normalize_optional_text(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    def _normalize_required_text(self, value: str, field_name: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} is required",
            )
        return normalized

    def _exclude_deleted(self, stmt):
        if hasattr(User, "deleted_at"):
            return stmt.where(User.deleted_at.is_(None))
        return stmt


user_repository = UserRepository()