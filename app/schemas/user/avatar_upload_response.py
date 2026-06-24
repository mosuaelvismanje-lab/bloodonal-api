# =========================================================
# FILE: app/schemas/user/avatar_upload_response.py
# =========================================================

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import (
    ConfigDict,
    HttpUrl,
)

from app.schemas.base import BaseSchema


class AvatarUploadResponse(BaseSchema):
    """
    =========================================================
    AVATAR UPLOAD RESPONSE DTO
    =========================================================
    Used after:
    - avatar upload
    - profile image update
    - CDN sync
    - media optimization
    =========================================================
    """

    model_config = ConfigDict(
        frozen=True,
    )

    # =====================================================
    # FILE INFO
    # =====================================================
    media_id: UUID

    user_id: UUID

    # =====================================================
    # FILE DETAILS
    # =====================================================
    file_name: str

    file_url: HttpUrl

    content_type: Optional[str] = None

    file_size: Optional[int] = None

    # =====================================================
    # IMAGE VARIANTS
    # =====================================================
    thumbnail_url: Optional[HttpUrl] = None

    optimized_url: Optional[HttpUrl] = None

    # =====================================================
    # STATUS
    # =====================================================
    success: bool = True

    message: str = "Avatar uploaded successfully"

    # =====================================================
    # AUDIT
    # =====================================================
    uploaded_at: datetime