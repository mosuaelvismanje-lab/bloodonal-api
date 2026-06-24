# =========================================================
# FILE: app/services/user/profile_service.py
# =========================================================

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.mapper.user_mapper import user_mapper
from app.repositories.user.user_repository import user_repository
from app.utils.datetime_utils import utc_now, utc_iso
from app.utils.image_utils import validate_image
from app.validators.auth_validator import AuthValidator
from app.validators.user_validator import UserValidator

logger = logging.getLogger(__name__)


class ProfileServiceError(Exception):
    """Base profile service exception."""


class ProfileNotFoundError(ProfileServiceError):
    """Raised when profile/user not found."""


class ProfileService:
    """
    =========================================================
    ENTERPRISE PROFILE SERVICE
    =========================================================
    """

    # =====================================================
    # CLEANER
    # =====================================================
    @staticmethod
    def _clean(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    # =====================================================
    # VALIDATE LOCAL IMAGE
    # =====================================================
    @staticmethod
    def _validate_local_avatar_reference(avatar_ref: str) -> None:
        path = Path(avatar_ref)
        if path.exists() and not validate_image(str(path)):
            raise ValueError("Invalid avatar image")

    # =====================================================
    # VALIDATE BLOOD GROUP (NEW)
    # =====================================================
    @staticmethod
    def _validate_blood_group(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        value = value.upper().strip()

        allowed = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
        if value not in allowed:
            raise ValueError("Invalid blood group")

        return value

    # =====================================================
    # GET PROFILE
    # =====================================================
    async def get_profile(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
    ) -> Optional[Any]:
        try:
            auth_uid = auth_uid.strip()

            user = await user_repository.get_by_auth_uid(
                db,
                auth_uid=auth_uid,
            )

            if not user:
                return None

            profile = getattr(user, "profile", None)

            if profile:
                return user_mapper.to_profile_response(profile)

            return user_mapper.to_user_response(user)

        except SQLAlchemyError as exc:
            logger.exception("[PROFILE_GET_DB_ERROR]")
            raise ProfileServiceError(
                "Database error while retrieving profile"
            ) from exc

        except Exception as exc:
            logger.exception("[PROFILE_GET_ERROR]")
            raise ProfileServiceError(
                "Failed to retrieve profile"
            ) from exc

    # =====================================================
    # UPDATE PROFILE (CLEAN + ENTERPRISE READY)
    # =====================================================
    async def update_profile(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        full_name: Optional[str] = None,
        username: Optional[str] = None,
        email: Optional[str] = None,
        bio: Optional[str] = None,
        gender: Optional[str] = None,
        avatar_url: Optional[str] = None,

        phone_number: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
        country: Optional[str] = None,
        blood_group: Optional[str] = None,
    ) -> Any:
        try:
            auth_uid = auth_uid.strip()

            # clean inputs
            full_name = self._clean(full_name)
            username = self._clean(username)
            email = self._clean(email)
            bio = self._clean(bio)
            gender = self._clean(gender)
            avatar_url = self._clean(avatar_url)

            phone_number = self._clean(phone_number)
            city = self._clean(city)
            state = self._clean(state)
            country = self._clean(country)
            blood_group = self._validate_blood_group(blood_group)

            user = await user_repository.get_by_auth_uid(
                db,
                auth_uid=auth_uid,
            )

            if not user:
                raise ProfileNotFoundError("User profile not found")

            # validate user fields
            if full_name:
                full_name = UserValidator.validate_full_name(full_name)

            if username:
                username = UserValidator.validate_username(username)

            if email:
                email = AuthValidator.validate_email(email)

            if bio:
                bio = UserValidator.validate_bio(bio)

            if gender:
                gender = UserValidator.validate_gender(gender)

            # update USER table
            if full_name and hasattr(user, "full_name"):
                user.full_name = full_name

            if username and hasattr(user, "username"):
                user.username = username

            if email:
                user.email = email.lower()

            if hasattr(user, "updated_at"):
                user.updated_at = utc_now()

            profile = getattr(user, "profile", None)

            if profile:

                # =========================
                # BASIC PROFILE
                # =========================
                if bio is not None:
                    profile.bio = bio

                if gender is not None:
                    profile.gender = gender

                if avatar_url is not None:
                    self._validate_local_avatar_reference(avatar_url)
                    profile.avatar_url = avatar_url

                # =========================
                # CONTACT INFO
                # =========================
                if phone_number is not None and hasattr(profile, "phone_number"):
                    profile.phone_number = phone_number

                # =========================
                # LOCATION
                # =========================
                if city is not None and hasattr(profile, "city"):
                    profile.city = city

                if state is not None and hasattr(profile, "state"):
                    profile.state = state

                if country is not None and hasattr(profile, "country"):
                    profile.country = country

                # =========================
                # BLOOD GROUP
                # =========================
                if blood_group is not None and hasattr(profile, "blood_group"):
                    profile.blood_group = blood_group

                if hasattr(profile, "updated_at"):
                    profile.updated_at = utc_now()

            await db.commit()
            await db.refresh(user)

            if profile:
                await db.refresh(profile)
                return user_mapper.to_profile_response(profile)

            return user_mapper.to_user_response(user)

        except (ProfileNotFoundError, ProfileServiceError):
            await db.rollback()
            raise

        except ValueError as exc:
            await db.rollback()
            logger.warning("[PROFILE_VALIDATION_ERROR] %s", exc)
            raise ProfileServiceError(str(exc)) from exc

        except SQLAlchemyError as exc:
            await db.rollback()
            logger.exception("[PROFILE_UPDATE_DB_ERROR]")
            raise ProfileServiceError(
                "Database error while updating profile"
            ) from exc

        except Exception as exc:
            await db.rollback()
            logger.exception("[PROFILE_UPDATE_ERROR]")
            raise ProfileServiceError(
                "Failed to update profile"
            ) from exc

    # =====================================================
    # UPDATE AVATAR
    # =====================================================
    async def update_avatar(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
        avatar_url: str,
    ) -> Dict[str, Any]:
        try:
            auth_uid = auth_uid.strip()
            avatar_url = avatar_url.strip()

            self._validate_local_avatar_reference(avatar_url)

            user = await user_repository.get_by_auth_uid(
                db,
                auth_uid=auth_uid,
            )

            if not user:
                raise ProfileNotFoundError("User not found")

            profile = getattr(user, "profile", None)

            if not profile:
                raise ProfileServiceError("Profile missing")

            profile.avatar_url = avatar_url

            if hasattr(profile, "updated_at"):
                profile.updated_at = utc_now()

            await db.commit()
            await db.refresh(profile)

            return {
                "success": True,
                "avatar_url": avatar_url,
                "updated_at": utc_iso(),
            }

        except Exception as exc:
            await db.rollback()
            logger.exception("[PROFILE_AVATAR_ERROR]")
            raise ProfileServiceError(str(exc)) from exc

    # =====================================================
    # DELETE AVATAR
    # =====================================================
    async def delete_avatar(
        self,
        db: AsyncSession,
        *,
        auth_uid: str,
    ) -> Dict[str, Any]:
        try:
            auth_uid = auth_uid.strip()

            user = await user_repository.get_by_auth_uid(
                db,
                auth_uid=auth_uid,
            )

            if not user:
                raise ProfileNotFoundError("User not found")

            profile = getattr(user, "profile", None)

            if not profile:
                raise ProfileServiceError("Profile missing")

            profile.avatar_url = None

            if hasattr(profile, "updated_at"):
                profile.updated_at = utc_now()

            await db.commit()
            await db.refresh(profile)

            return {
                "success": True,
                "message": "Avatar removed",
                "updated_at": utc_iso(),
            }

        except Exception as exc:
            await db.rollback()
            logger.exception("[PROFILE_DELETE_AVATAR_ERROR]")
            raise ProfileServiceError(str(exc)) from exc

    # =====================================================
    # HEALTH CHECK
    # =====================================================
    async def health_check(self) -> Dict[str, Any]:
        return {
            "service": "profile_service",
            "status": "healthy",
            "time": utc_iso(),
        }


profile_service = ProfileService()