# =========================================================
# FILE: app/repositories/user/profile_repository.py
# =========================================================

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user.user_profile import UserProfile
from app.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


# =========================================================
# EXCEPTIONS
# =========================================================
class ProfileRepositoryError(Exception):
    """
    Base repository exception.
    """


# =========================================================
# PROFILE REPOSITORY
# =========================================================
class ProfileRepository:
    """
    =========================================================
    PROFILE REPOSITORY
    =========================================================

    Handles:
    ---------------------------------------------------------
    - User profile persistence
    - Profile onboarding
    - Avatar updates
    - Bio & identity updates
    - Soft-delete aware reads
    - Enterprise-safe updates
    =========================================================
    """

    # =====================================================
    # GET PROFILE BY USER ID
    # =====================================================
    async def get_by_user_id(
        self,
        db: AsyncSession,
        user_id: UUID,
    ) -> Optional[UserProfile]:

        stmt = select(UserProfile).where(
            UserProfile.user_id == user_id
        )

        stmt = self._exclude_deleted(stmt)

        result = await db.execute(stmt)

        return result.scalar_one_or_none()

    # =====================================================
    # GET PROFILE BY PROFILE ID
    # =====================================================
    async def get_by_id(
        self,
        db: AsyncSession,
        profile_id: UUID,
    ) -> Optional[UserProfile]:

        stmt = select(UserProfile).where(
            UserProfile.id == profile_id
        )

        stmt = self._exclude_deleted(stmt)

        result = await db.execute(stmt)

        return result.scalar_one_or_none()

    # =====================================================
    # UPSERT PROFILE
    # =====================================================
    async def upsert_profile(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        **fields: Any,
    ) -> UserProfile:

        try:
            profile = await self.get_by_user_id(
                db,
                user_id,
            )

            now = utc_now()

            # =============================================
            # CLEAN INPUT FIELDS
            # =============================================
            clean_fields = self._clean_fields(
                fields
            )

            # =============================================
            # CREATE PROFILE
            # =============================================
            if profile is None:

                profile = UserProfile(
                    user_id=user_id,
                    **clean_fields,
                )

                if hasattr(profile, "created_at"):
                    profile.created_at = now

                if hasattr(profile, "updated_at"):
                    profile.updated_at = now

                db.add(profile)

                logger.info(
                    "[PROFILE_CREATED] user_id=%s",
                    user_id,
                )

            # =============================================
            # UPDATE PROFILE
            # =============================================
            else:

                for key, value in clean_fields.items():

                    if (
                        hasattr(profile, key)
                        and value is not None
                    ):
                        setattr(
                            profile,
                            key,
                            value,
                        )

                if hasattr(profile, "updated_at"):
                    profile.updated_at = now

                logger.info(
                    "[PROFILE_UPDATED] user_id=%s",
                    user_id,
                )

            await db.commit()

            await db.refresh(profile)

            return profile

        except SQLAlchemyError as exc:

            await db.rollback()

            logger.exception(
                "[PROFILE_UPSERT_DB_ERROR]"
            )

            raise ProfileRepositoryError(
                "Profile update failed"
            ) from exc

        except Exception as exc:

            await db.rollback()

            logger.exception(
                "[PROFILE_UPSERT_ERROR]"
            )

            raise ProfileRepositoryError(
                "Unexpected profile repository failure"
            ) from exc

    # =====================================================
    # UPDATE AVATAR
    # =====================================================
    async def update_avatar(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        avatar_url: str,
    ) -> Optional[UserProfile]:

        try:
            profile = await self.get_by_user_id(
                db,
                user_id,
            )

            if not profile:
                return None

            profile.avatar_url = (
                avatar_url.strip()
            )

            if hasattr(profile, "updated_at"):
                profile.updated_at = utc_now()

            await db.commit()

            await db.refresh(profile)

            logger.info(
                "[PROFILE_AVATAR_UPDATED] user_id=%s",
                user_id,
            )

            return profile

        except SQLAlchemyError as exc:

            await db.rollback()

            logger.exception(
                "[PROFILE_AVATAR_DB_ERROR]"
            )

            raise ProfileRepositoryError(
                "Avatar update failed"
            ) from exc

    # =====================================================
    # DELETE AVATAR
    # =====================================================
    async def delete_avatar(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
    ) -> bool:

        try:
            profile = await self.get_by_user_id(
                db,
                user_id,
            )

            if not profile:
                return False

            profile.avatar_url = None

            if hasattr(profile, "updated_at"):
                profile.updated_at = utc_now()

            await db.commit()

            logger.info(
                "[PROFILE_AVATAR_DELETED] user_id=%s",
                user_id,
            )

            return True

        except SQLAlchemyError as exc:

            await db.rollback()

            logger.exception(
                "[PROFILE_DELETE_AVATAR_DB_ERROR]"
            )

            raise ProfileRepositoryError(
                "Avatar deletion failed"
            ) from exc

    # =====================================================
    # DELETE PROFILE (SOFT DELETE)
    # =====================================================
    async def soft_delete_profile(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
    ) -> bool:

        try:
            profile = await self.get_by_user_id(
                db,
                user_id,
            )

            if not profile:
                return False

            if hasattr(profile, "deleted_at"):
                profile.deleted_at = utc_now()

            if hasattr(profile, "updated_at"):
                profile.updated_at = utc_now()

            await db.commit()

            logger.info(
                "[PROFILE_SOFT_DELETED] user_id=%s",
                user_id,
            )

            return True

        except SQLAlchemyError as exc:

            await db.rollback()

            logger.exception(
                "[PROFILE_DELETE_DB_ERROR]"
            )

            raise ProfileRepositoryError(
                "Profile deletion failed"
            ) from exc

    # =====================================================
    # PROFILE EXISTS
    # =====================================================
    async def exists(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
    ) -> bool:

        profile = await self.get_by_user_id(
            db,
            user_id,
        )

        return profile is not None

    # =====================================================
    # PROFILE COMPLETENESS
    # =====================================================
    def profile_completion_score(
        self,
        profile: UserProfile,
    ) -> int:

        fields = [
            getattr(
                profile,
                "first_name",
                None,
            ),
            getattr(
                profile,
                "last_name",
                None,
            ),
            getattr(
                profile,
                "avatar_url",
                None,
            ),
            getattr(
                profile,
                "bio",
                None,
            ),
            getattr(
                profile,
                "gender",
                None,
            ),
            getattr(
                profile,
                "date_of_birth",
                None,
            ),
        ]

        total = len(fields)

        completed = len(
            [
                field
                for field in fields
                if field
            ]
        )

        return int(
            (completed / total) * 100
        )

    # =====================================================
    # CLEAN FIELDS
    # =====================================================
    def _clean_fields(
        self,
        fields: Dict[str, Any],
    ) -> Dict[str, Any]:

        cleaned: Dict[str, Any] = {}

        for key, value in fields.items():

            if isinstance(value, str):
                value = value.strip()

            cleaned[key] = value

        return cleaned

    # =====================================================
    # EXCLUDE SOFT DELETED
    # =====================================================
    def _exclude_deleted(
        self,
        stmt,
    ):

        if hasattr(
            UserProfile,
            "deleted_at",
        ):
            stmt = stmt.where(
                UserProfile.deleted_at.is_(None)
            )

        return stmt


# =========================================================
# SINGLETON
# =========================================================
profile_repository = ProfileRepository()