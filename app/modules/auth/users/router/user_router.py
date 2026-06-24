from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import MockUser, get_current_user, get_db
from app.models.user.user import User

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


# =========================================================
# REQUEST MODELS
# =========================================================
class InitializeProfileRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    uid: str = Field(..., min_length=1, max_length=128)
    email: EmailStr
    platform: str = Field(..., min_length=2, max_length=50)
    created_at: str


# =========================================================
# RESPONSE MODELS
# =========================================================
class InitializeProfileResponse(BaseModel):
    success: bool
    message: str
    user_id: str
    email: EmailStr
    created: bool
    updated_at: datetime


# =========================================================
# HELPERS
# =========================================================
def _normalize_platform(value: str) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="platform is required",
        )
    return normalized


def _parse_created_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid created_at format",
        ) from exc


def _safe_uuid(raw_uid: str) -> uuid.UUID:
    """
    Converts Firebase UID into a deterministic UUID.
    """
    normalized = (raw_uid or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uid is required",
        )

    try:
        return uuid.UUID(normalized)
    except Exception:
        namespace = uuid.uuid5(uuid.NAMESPACE_DNS, "bloodonal")
        return uuid.uuid5(namespace, normalized)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _find_existing_user(
    db: AsyncSession,
    *,
    auth_uid: str,
    email: str,
) -> User | None:
    stmt = select(User).where(
        or_(
            User.auth_uid == auth_uid,
            User.email == email,
        )
    )

    if hasattr(User, "deleted_at"):
        stmt = stmt.where(User.deleted_at.is_(None))

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _build_response(
    *,
    user: User,
    created: bool,
    message: str,
) -> InitializeProfileResponse:
    return InitializeProfileResponse(
        success=True,
        message=message,
        user_id=str(user.uid),
        email=user.email,
        created=created,
        updated_at=user.updated_at,
    )


# =========================================================
# INITIALIZE PROFILE
# =========================================================
@router.post(
    "/initialize",
    response_model=InitializeProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initialize_profile(
    payload: InitializeProfileRequest,
    current_user: MockUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Production-safe profile initialization endpoint.

    Behavior:
    - Validates Firebase identity
    - Prevents duplicate profile creation
    - Refreshes existing profile if present
    - Aligns with the current User ORM model
    - Safe to call multiple times
    """
    payload_email = payload.email.lower().strip()
    current_email = (current_user.email or "").lower().strip()

    if not current_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user email is missing",
        )

    if payload_email != current_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email mismatch detected",
        )

    normalized_platform = _normalize_platform(payload.platform)
    normalized_auth_uid = payload.uid.strip()
    created_at = _parse_created_at(payload.created_at)
    now = _now_utc()
    user_uuid = _safe_uuid(normalized_auth_uid)

    try:
        existing_user = await _find_existing_user(
            db,
            auth_uid=normalized_auth_uid,
            email=payload_email,
        )

        if existing_user is not None:
            existing_user.auth_uid = normalized_auth_uid
            existing_user.email = payload_email
            existing_user.name = (current_user.name or existing_user.name or "Unknown User").strip()
            existing_user.role = existing_user.role or "user"
            existing_user.is_active = True

            if hasattr(existing_user, "is_verified"):
                existing_user.is_verified = getattr(existing_user, "is_verified", False)
            if hasattr(existing_user, "auth_provider"):
                existing_user.auth_provider = "firebase"
            if hasattr(existing_user, "platform"):
                existing_user.platform = normalized_platform
            if hasattr(existing_user, "last_login_at"):
                existing_user.last_login_at = now
            if hasattr(existing_user, "last_seen_at"):
                existing_user.last_seen_at = now
            if hasattr(existing_user, "updated_at"):
                existing_user.updated_at = now
            if hasattr(existing_user, "deleted_at"):
                existing_user.deleted_at = None
            if hasattr(existing_user, "login_count"):
                existing_user.login_count = (existing_user.login_count or 0) + 1

            await db.commit()
            await db.refresh(existing_user)

            logger.info(
                "Profile refreshed for user=%s email=%s",
                existing_user.uid,
                existing_user.email,
            )

            return _build_response(
                user=existing_user,
                created=False,
                message="Profile already exists",
            )

        new_user = User(
            uid=user_uuid,
            auth_uid=normalized_auth_uid,
            email=payload_email,
            name=(current_user.name or "Unknown User").strip(),
            role="user",
            platform=normalized_platform,
            is_active=True,
            is_verified=False,
            auth_provider="firebase",
            created_at=created_at,
            updated_at=now,
            last_login_at=now,
            last_seen_at=now,
            login_count=1,
        )

        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        logger.info(
            "Profile initialized for user=%s email=%s",
            new_user.uid,
            new_user.email,
        )

        return _build_response(
            user=new_user,
            created=True,
            message="Profile initialized successfully",
        )

    except SQLAlchemyError as exc:
        await db.rollback()
        logger.exception("Database error during profile initialization")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        await db.rollback()
        logger.exception("Unexpected profile initialization error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected server error",
        ) from exc