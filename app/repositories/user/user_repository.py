from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID, uuid5, NAMESPACE_DNS

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user.user import User

logger = logging.getLogger(__name__)


class UserRepository:
    """
    =========================================================
    USER REPOSITORY (ENTERPRISE CORE)
    =========================================================
    Responsibilities:
    - Firebase sync persistence
    - User lookup strategies
    - Soft-delete aware queries
    - Login tracking support
    - Profile bootstrap

    Security ownership:
    - UserSecurity should be handled by:
      security_repository.py
      security_service.py
      auth_service.py
      session_service.py
    - Do not put security logic here.
    =========================================================
    """

    # =====================================================
    # READ
    # =====================================================
    async def get_by_id(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> Optional[User]:
        stmt = select(User).where(User.uid == user_id)
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_auth_uid(
        self,
        db: AsyncSession,
        auth_uid: str,
    ) -> Optional[User]:
        normalized = self._normalize_text(auth_uid)
        if not normalized:
            return None

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
        if not normalized:
            return None

        stmt = select(User).where(User.email == normalized)
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_auth_or_email(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        email: str,
    ) -> Optional[User]:
        normalized_auth_uid = self._normalize_text(auth_uid)
        normalized_email = self._normalize_email(email)

        if not normalized_auth_uid and not normalized_email:
            return None

        conditions = []
        if normalized_auth_uid:
            conditions.append(User.auth_uid == normalized_auth_uid)
        if normalized_email:
            conditions.append(User.email == normalized_email)

        stmt = select(User).where(or_(*conditions))
        stmt = self._exclude_deleted(stmt)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =====================================================
    # UPSERT (FIREBASE SYNC)
    # =====================================================
    async def upsert_user(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        email: str,
        name: str,
        role: str = "user",
    ) -> Tuple[User, bool]:
        """
        Returns:
            (user, created)
        """
        try:
            normalized_auth_uid = self._normalize_text(auth_uid)
            normalized_email = self._normalize_email(email)
            normalized_name = self._normalize_text(name) or "Unknown User"
            normalized_role = self._normalize_text(role) or "user"

            user = await self.get_by_auth_uid(db, normalized_auth_uid)
            created = False
            now = datetime.now(timezone.utc)

            if user is None:
                user = await self.get_by_email(db, normalized_email)
                created = user is None

            if user is None:
                user = User(
                    uid=self._stable_uuid(normalized_auth_uid),
                    auth_uid=normalized_auth_uid,
                    email=normalized_email,
                    name=normalized_name,
                    role=normalized_role,
                    is_active=True,
                    is_verified=False,
                    created_at=now,
                    updated_at=now,
                )
                db.add(user)
            else:
                user.email = normalized_email
                user.name = normalized_name
                user.role = normalized_role
                user.updated_at = now

            await db.commit()
            await db.refresh(user)

            return user, created

        except SQLAlchemyError as e:
            await db.rollback()
            logger.exception("User upsert failed")
            raise RuntimeError("User upsert failed") from e

    # =====================================================
    # UPDATE FCM
    # =====================================================
    async def update_fcm_token(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        token: str,
    ) -> None:
        user = await self.get_by_id(db, user_id)
        if not user:
            return

        normalized_token = self._normalize_text(token)
        if not normalized_token:
            return

        user.fcm_token = normalized_token
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

    # =====================================================
    # LOGIN TRACKING
    # =====================================================
    async def mark_login(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
    ) -> None:
        user = await self.get_by_id(db, user_id)
        if not user:
            return

        user.last_login_at = datetime.now(timezone.utc)
        user.login_count = (user.login_count or 0) + 1
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

    # =====================================================
    # HELPERS
    # =====================================================
    def _stable_uuid(self, raw: str) -> UUID:
        try:
            return UUID(raw)
        except Exception:
            return uuid5(NAMESPACE_DNS, f"user:{raw}")

    def _normalize_text(self, value: str | None) -> str:
        return (value or "").strip()

    def _normalize_email(self, value: str | None) -> str:
        return self._normalize_text(value).lower()

    def _exclude_deleted(self, stmt):
        if hasattr(User, "deleted_at"):
            return stmt.where(User.deleted_at.is_(None))
        return stmt


user_repository = UserRepository()