# =========================================================
# FILE: app/services/upload_service.py
# =========================================================

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Literal

from fastapi import HTTPException, UploadFile

from app.utils.file_utils import (
    ensure_directory,
    generate_secure_filename,
    get_file_size_mb,
    validate_document_extension,
    validate_image_extension,
)
from app.utils.image_utils import validate_image as validate_image_file

logger = logging.getLogger(__name__)


class UploadService:
    """
    =========================================================
    ENTERPRISE UPLOAD SERVICE
    =========================================================

    Features:
    ---------------------------------------------------------
    - Secure file naming
    - Extension validation via utils
    - Actual image verification via Pillow
    - File size validation
    - Safe disk storage
    - Future-ready for S3 / Cloud storage
    =========================================================
    """

    MAX_FILE_SIZE_MB: int = 10

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _validate_file(
        self,
        file: UploadFile,
        *,
        kind: Literal["image", "document", "any"] = "image",
    ) -> None:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Invalid file name")

        filename = file.filename.lower()

        if kind == "image":
            if not validate_image_extension(filename):
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported image type",
                )
        elif kind == "document":
            if not validate_document_extension(filename):
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported document type",
                )
        else:
            if not (
                validate_image_extension(filename)
                or validate_document_extension(filename)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Unsupported file type",
                )

    def _validate_size(self, size_bytes: int) -> None:
        size_mb = get_file_size_mb(size_bytes)
        if size_mb > self.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({size_mb} MB)",
            )

    async def save_file(
        self,
        file: UploadFile,
        upload_dir: str = "uploads",
        prefix: Optional[str] = None,
        kind: Literal["image", "document", "any"] = "image",
        verify_image_content: bool = True,
    ) -> str:
        """
        Saves file securely to disk and returns the saved path.
        """

        self._validate_file(file, kind=kind)
        ensure_directory(upload_dir)

        content = await file.read()
        self._validate_size(len(content))

        secure_name = generate_secure_filename(
            file.filename,
            prefix=prefix,
        )

        file_path = Path(upload_dir) / secure_name

        try:
            with open(file_path, "wb") as f:
                f.write(content)

            if kind == "image" and verify_image_content:
                if not validate_image_file(str(file_path)):
                    try:
                        file_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid image content",
                    )

            logger.info(
                "[UPLOAD_SUCCESS] file=%s size_mb=%.2f",
                secure_name,
                get_file_size_mb(len(content)),
            )

            return str(file_path)

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("[UPLOAD_FAILED] %s", exc)
            try:
                file_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise HTTPException(
                status_code=500,
                detail="Failed to save file",
            ) from exc


upload_service = UploadService()