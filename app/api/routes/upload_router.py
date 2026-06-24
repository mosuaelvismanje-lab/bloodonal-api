# =========================================================
# FILE: app/api/routes/upload_routes.py
# =========================================================

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db

from app.schemas.user.avatar_upload_response import AvatarUploadResponse
from app.services.user import upload_service

from app.services.user.profile_service import profile_service

from app.validators.upload_validator import upload_validator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/uploads",
    tags=["Uploads"],
)


# =========================================================
# AVATAR UPLOAD
# =========================================================
@router.post(
    "/avatar",
    response_model=AvatarUploadResponse,
)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Upload user avatar and update profile.
    """

    try:
        # =================================================
        # VALIDATE FILE (EXTRA LAYER)
        # =================================================
        await upload_validator.validate_image(file)

        # =================================================
        # UPLOAD FILE (LOCAL / FUTURE S3 READY)
        # =================================================
        upload_result = await upload_service.save_file(
            file=file,
            upload_dir="uploads/avatars",
            prefix="avatar",
        )

        # =================================================
        # UPDATE PROFILE AVATAR
        # =================================================
        await profile_service.update_avatar(
            db,
            auth_uid=current_user["uid"],
            avatar_url=upload_result,
        )

        return AvatarUploadResponse(
            success=True,
            message="Avatar uploaded successfully",
            avatar_url=upload_result,
            file_name=upload_result.split("/")[-1],
            file_size=None,  # optional if you want to extend upload_service later
        )

    except ValueError as exc:
        logger.warning("[UPLOAD_VALIDATION_ERROR] %s", exc)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("[AVATAR_UPLOAD_FAILED] %s", exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Avatar upload failed",
        ) from exc


# =========================================================
# DOCUMENT UPLOAD
# =========================================================
@router.post("/document")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Upload user documents (PDF, DOC, etc.)
    """

    try:
        await upload_validator.validate_document(file)

        upload_result = await upload_service.save_file(
            file=file,
            upload_dir="uploads/documents",
            prefix="doc",
        )

        return {
            "success": True,
            "url": upload_result,
            "file_name": upload_result.split("/")[-1],
        }

    except ValueError as exc:
        logger.warning("[DOCUMENT_VALIDATION_ERROR] %s", exc)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        logger.exception("[DOCUMENT_UPLOAD_FAILED] %s", exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document upload failed",
        ) from exc


# =========================================================
# DELETE FILE
# =========================================================
@router.delete("/{file_id}")
async def delete_uploaded_file(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Delete uploaded file by ID (future: storage abstraction).
    """

    try:
        deleted = await upload_service.delete_file(
            file_id=file_id,
            user_id=current_user["uid"],
        )

        return {
            "success": deleted,
            "file_id": file_id,
        }

    except Exception as exc:
        logger.exception("[FILE_DELETE_FAILED] %s", exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file",
        ) from exc