# =========================================================
# FILE: app/services/storage/s3_service.py
# =========================================================

from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from app.utils.file_utils import (
    get_extension,
    generate_secure_filename,
    get_file_size_mb,
)

# =========================================================
# ENV
# =========================================================
load_dotenv()

logger = logging.getLogger("bloodonal.s3")


# =========================================================
# SERVICE
# =========================================================
class S3Service:
    """
    =========================================================
    ENTERPRISE AWS S3 STORAGE SERVICE
    =========================================================

    Features:
    ---------------------------------------------------------
    - Secure file upload
    - Signed public/private upload support
    - Metadata detection
    - Safe delete / existence check
    - Clean integration with file_utils layer
    =========================================================
    """

    def __init__(self):
        self.bucket = os.getenv("AWS_S3_BUCKET")

        self.enabled: bool = bool(
            self.bucket
            and os.getenv("AWS_ACCESS_KEY_ID")
            and os.getenv("AWS_SECRET_ACCESS_KEY")
        )

        self.region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

        self.client = boto3.client(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region,
        )

    # =====================================================
    # STATUS
    # =====================================================
    def is_ready(self) -> bool:
        return self.enabled

    # =====================================================
    # UPLOAD FILE
    # =====================================================
    async def upload_file(
        self,
        *,
        file_path: str,
        folder: str = "uploads",
        object_name: Optional[str] = None,
        public: bool = True,
    ) -> dict[str, Any]:
        """
        Upload a local file to S3.
        """

        if not self.enabled:
            raise RuntimeError("S3 not configured")

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            # =================================================
            # SECURE FILE NAME
            # =================================================
            extension = get_extension(str(path))
            filename = object_name or generate_secure_filename(
                str(path.name)
            )

            key = f"{folder}/{filename}"

            # =================================================
            # MIME TYPE
            # =================================================
            content_type = (
                mimetypes.guess_type(str(path))[0]
                or "application/octet-stream"
            )

            # =================================================
            # S3 UPLOAD OPTIONS
            # =================================================
            extra_args = {
                "ContentType": content_type,
            }

            if public:
                extra_args["ACL"] = "public-read"

            # =================================================
            # UPLOAD
            # =================================================
            self.client.upload_file(
                Filename=str(path),
                Bucket=self.bucket,
                Key=key,
                ExtraArgs=extra_args,
            )

            url = (
                f"https://{self.bucket}.s3."
                f"{self.region}.amazonaws.com/{key}"
            )

            logger.info(
                "[S3_UPLOAD_SUCCESS] key=%s size_mb=%.2f",
                key,
                get_file_size_mb(path.stat().st_size),
            )

            return {
                "provider": "s3",
                "bucket": self.bucket,
                "key": key,
                "url": url,
                "content_type": content_type,
                "size_mb": get_file_size_mb(path.stat().st_size),
                "extension": extension,
            }

        except Exception as exc:
            logger.exception("[S3_UPLOAD_FAILED] %s", exc)
            raise RuntimeError("S3 upload failed") from exc

    # =====================================================
    # DELETE FILE
    # =====================================================
    async def delete_file(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Delete file from S3 bucket.
        """

        if not self.enabled:
            return False

        try:
            self.client.delete_object(
                Bucket=self.bucket,
                Key=key,
            )

            logger.info("[S3_DELETE] key=%s", key)
            return True

        except ClientError as exc:
            logger.warning("[S3_DELETE_FAILED] %s", exc)
            return False

    # =====================================================
    # FILE EXISTS CHECK
    # =====================================================
    async def file_exists(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Check if file exists in S3.
        """

        if not self.enabled:
            return False

        try:
            self.client.head_object(
                Bucket=self.bucket,
                Key=key,
            )
            return True

        except Exception:
            return False


# =========================================================
# SINGLETON
# =========================================================
s3_service = S3Service()