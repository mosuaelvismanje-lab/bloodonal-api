# =========================================================
# FILE: app/services/storage/firebase_storage_service.py
# =========================================================

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from firebase_admin import storage

from app.firebase_client import is_firebase_ready

from app.utils.file_utils import (
    validate_image_extension,
    validate_document_extension,
    generate_secure_filename,
    get_file_size_mb,
    ensure_directory,
)

# =========================================================
# ENV
# =========================================================
load_dotenv()

logger = logging.getLogger("bloodonal.firebase_storage")


# =========================================================
# SERVICE
# =========================================================
class FirebaseStorageService:
    """
    =========================================================
    ENTERPRISE FIREBASE STORAGE SERVICE
    =========================================================

    Features:
    ---------------------------------------------------------
    - Secure file uploads
    - Image + document validation
    - Public/private control
    - Safe filename generation
    - File existence checks
    =========================================================
    """

    def __init__(self):
        self.bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
        self.enabled = bool(self.bucket_name)

    # =====================================================
    # STATUS
    # =====================================================
    def is_ready(self) -> bool:
        return self.enabled and is_firebase_ready()

    # =====================================================
    # VALIDATION LAYER
    # =====================================================
    def _validate_file(self, path: Path) -> None:
        """
        Validate file type using enterprise rules.
        """

        filename = path.name

        if validate_image_extension(filename):
            return

        if validate_document_extension(filename):
            return

        raise ValueError(f"Unsupported file type: {filename}")

    # =====================================================
    # UPLOAD FILE
    # =====================================================
    async def upload_file(
        self,
        *,
        file_path: str,
        folder: str = "uploads",
        filename: Optional[str] = None,
        make_public: bool = True,
    ) -> dict[str, Any]:

        if not self.is_ready():
            raise RuntimeError("Firebase Storage not ready")

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(file_path)

        try:
            # =================================================
            # VALIDATE FILE TYPE
            # =================================================
            self._validate_file(path)

            # =================================================
            # ENSURE SAFE FILENAME
            # =================================================
            final_filename = filename or generate_secure_filename(path.name)

            blob_name = f"{folder}/{final_filename}"

            bucket = storage.bucket()
            blob = bucket.blob(blob_name)

            blob.upload_from_filename(str(path))

            if make_public:
                blob.make_public()

            logger.info(
                "[FIREBASE_UPLOAD_SUCCESS] blob=%s",
                blob_name,
            )

            return {
                "provider": "firebase_storage",
                "bucket": bucket.name,
                "blob": blob_name,
                "url": blob.public_url,
                "size_mb": get_file_size_mb(path.stat().st_size),
                "filename": final_filename,
            }

        except Exception as exc:
            logger.exception(
                "[FIREBASE_UPLOAD_FAILED] %s",
                exc,
            )
            raise RuntimeError("Firebase upload failed") from exc

    # =====================================================
    # DELETE FILE
    # =====================================================
    async def delete_file(
        self,
        *,
        blob_name: str,
    ) -> bool:

        if not self.is_ready():
            return False

        try:
            bucket = storage.bucket()
            blob = bucket.blob(blob_name)

            blob.delete()

            logger.info(
                "[FIREBASE_DELETE_SUCCESS] %s",
                blob_name,
            )

            return True

        except Exception as exc:
            logger.warning(
                "[FIREBASE_DELETE_FAILED] %s",
                exc,
            )
            return False

    # =====================================================
    # FILE EXISTS
    # =====================================================
    async def file_exists(
        self,
        *,
        blob_name: str,
    ) -> bool:

        if not self.is_ready():
            return False

        try:
            bucket = storage.bucket()
            blob = bucket.blob(blob_name)

            return blob.exists()

        except Exception:
            return False


# =========================================================
# SINGLETON
# =========================================================
firebase_storage_service = FirebaseStorageService()