# =========================================================
# FILE: app/validators/upload_validator.py
# =========================================================

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, UploadFile, status


class UploadValidator:
    """
    Enterprise Upload Validator

    Responsibilities:
    -----------------------------------------------------
    - Validate file extension
    - Validate MIME type
    - Validate size
    - Prevent malicious uploads
    """

    IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".mov",
        ".avi",
    }

    DOCUMENT_EXTENSIONS = {
        ".pdf",
        ".doc",
        ".docx",
    }

    MAX_IMAGE_SIZE = 10 * 1024 * 1024
    MAX_VIDEO_SIZE = 50 * 1024 * 1024
    MAX_DOCUMENT_SIZE = 20 * 1024 * 1024

    @classmethod
    async def validate_image(
        cls,
        file: UploadFile,
    ) -> None:
        await cls._validate(
            file=file,
            allowed_extensions=cls.IMAGE_EXTENSIONS,
            max_size=cls.MAX_IMAGE_SIZE,
            allowed_mime_prefix="image/",
        )

    @classmethod
    async def validate_video(
        cls,
        file: UploadFile,
    ) -> None:
        await cls._validate(
            file=file,
            allowed_extensions=cls.VIDEO_EXTENSIONS,
            max_size=cls.MAX_VIDEO_SIZE,
            allowed_mime_prefix="video/",
        )

    @classmethod
    async def validate_document(
        cls,
        file: UploadFile,
    ) -> None:
        await cls._validate(
            file=file,
            allowed_extensions=cls.DOCUMENT_EXTENSIONS,
            max_size=cls.MAX_DOCUMENT_SIZE,
            allowed_mime_prefix=None,
        )

    @classmethod
    async def _validate(
        cls,
        *,
        file: UploadFile,
        allowed_extensions: set[str],
        max_size: int,
        allowed_mime_prefix: Optional[str],
    ) -> None:

        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename missing",
            )

        extension = Path(file.filename).suffix.lower()

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file extension: {extension}",
            )

        mime_type = file.content_type or mimetypes.guess_type(
            file.filename
        )[0]

        if (
            allowed_mime_prefix
            and mime_type
            and not mime_type.startswith(
                allowed_mime_prefix
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid MIME type",
            )

        content = await file.read()

        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File too large",
            )

        await file.seek(0)


upload_validator = UploadValidator()