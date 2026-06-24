# =========================================================
# FILE: app/services/storage/cloudinary_service.py
# =========================================================

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import cloudinary
import cloudinary.api
import cloudinary.uploader
from dotenv import load_dotenv

from app.utils.file_utils import (
    generate_secure_filename,
    get_file_size_mb,
    validate_document_extension,
    validate_image_extension,
)
from app.utils.image_utils import validate_image

load_dotenv()

logger = logging.getLogger("bloodonal.cloudinary")

CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
API_KEY = os.getenv("CLOUDINARY_API_KEY")
API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
    secure=True,
)


class CloudinaryService:
    """
    =========================================================
    ENTERPRISE CLOUDINARY STORAGE SERVICE
    =========================================================
    - Secure upload (images + documents)
    - File validation integration
    - Metadata response normalization
    - Safe failure handling
    =========================================================
    """

    def __init__(self):
        self.enabled: bool = all([CLOUD_NAME, API_KEY, API_SECRET])

    def is_ready(self) -> bool:
        return self.enabled

    def _validate_file(self, file_path: Path, resource_type: str) -> None:
        filename = file_path.name.lower()

        if resource_type == "image":
            if not validate_image_extension(filename):
                raise ValueError(f"Invalid image file type: {filename}")
            if not validate_image(str(file_path)):
                raise ValueError(f"Invalid image content: {filename}")
            return

        if resource_type in ("raw", "document"):
            if not validate_document_extension(filename):
                raise ValueError(f"Invalid document file type: {filename}")
            return

        if not (
            validate_image_extension(filename)
            or validate_document_extension(filename)
        ):
            raise ValueError(f"Unsupported file type: {filename}")

    async def upload_file(
        self,
        *,
        file_path: str,
        folder: str = "bloodonal",
        public_id: Optional[str] = None,
        resource_type: str = "auto",
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Cloudinary not configured")

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            self._validate_file(path, resource_type)

            filename = public_id or generate_secure_filename(path.name)

            result = cloudinary.uploader.upload(
                file=str(path),
                folder=folder,
                public_id=filename,
                overwrite=False,
                resource_type=resource_type,
            )

            logger.info(
                "[CLOUDINARY_UPLOAD_SUCCESS] public_id=%s",
                result.get("public_id"),
            )

            return {
                "provider": "cloudinary",
                "public_id": result.get("public_id"),
                "url": result.get("secure_url"),
                "width": result.get("width"),
                "height": result.get("height"),
                "format": result.get("format"),
                "bytes": result.get("bytes"),
                "size_mb": get_file_size_mb(result.get("bytes") or 0),
                "resource_type": result.get("resource_type"),
                "created_at": result.get("created_at"),
            }

        except Exception as exc:
            logger.exception("[CLOUDINARY_UPLOAD_FAILED] %s", exc)
            raise RuntimeError("Cloudinary upload failed") from exc

    async def delete_file(
        self,
        *,
        public_id: str,
        resource_type: str = "image",
    ) -> bool:
        if not self.enabled:
            logger.warning("Cloudinary disabled - delete skipped")
            return False

        try:
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type,
            )

            success = result.get("result") == "ok"

            logger.info(
                "[CLOUDINARY_DELETE] public_id=%s result=%s",
                public_id,
                result.get("result"),
            )

            return success

        except Exception as exc:
            logger.exception("[CLOUDINARY_DELETE_FAILED] %s", exc)
            return False

    async def get_file_info(
        self,
        *,
        public_id: str,
    ) -> Optional[dict[str, Any]]:
        if not self.enabled:
            return None

        try:
            result = cloudinary.api.resource(public_id)

            return {
                "public_id": result.get("public_id"),
                "url": result.get("secure_url"),
                "format": result.get("format"),
                "bytes": result.get("bytes"),
                "size_mb": get_file_size_mb(result.get("bytes") or 0),
                "width": result.get("width"),
                "height": result.get("height"),
                "created_at": result.get("created_at"),
            }

        except Exception as exc:
            logger.warning("[CLOUDINARY_INFO_FAILED] %s", exc)
            return None


cloudinary_service = CloudinaryService()