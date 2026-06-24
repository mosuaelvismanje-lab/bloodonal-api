# =========================================================
# FILE: app/utils/file_utils.py
# =========================================================

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Optional


ALLOWED_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

ALLOWED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
}


def get_extension(
    filename: str,
) -> str:
    return Path(filename).suffix.lower()


def validate_image_extension(
    filename: str,
) -> bool:
    return get_extension(filename) in ALLOWED_IMAGE_EXTENSIONS


def validate_document_extension(
    filename: str,
) -> bool:
    return get_extension(filename) in ALLOWED_DOCUMENT_EXTENSIONS


def generate_secure_filename(
    filename: str,
    prefix: Optional[str] = None,
) -> str:

    ext = get_extension(filename)

    token = secrets.token_hex(16)

    if prefix:
        return f"{prefix}_{token}{ext}"

    return f"{token}{ext}"


def get_file_size_mb(
    file_size_bytes: int,
) -> float:
    return round(file_size_bytes / (1024 * 1024), 2)


def ensure_directory(
    path: str,
) -> None:
    os.makedirs(path, exist_ok=True)