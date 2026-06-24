# =========================================================
# FILE: app/utils/token_utils.py
# =========================================================

from __future__ import annotations

import secrets
from typing import Optional
from uuid import UUID, uuid5, NAMESPACE_DNS


def generate_token(
    length: int = 32,
) -> str:
    return secrets.token_urlsafe(length)


def generate_numeric_otp(
    digits: int = 6,
) -> str:
    if digits <= 0:
        raise ValueError("digits must be positive")

    upper = 10 ** digits

    return str(secrets.randbelow(upper)).zfill(digits)


def generate_correlation_id() -> str:
    return secrets.token_hex(16)


def stable_uuid(
    raw: str,
    namespace: Optional[str] = None,
) -> UUID:
    """
    Generates stable UUID from string.
    """

    try:
        return UUID(str(raw))
    except Exception:
        prefix = namespace or "app"
        return uuid5(
            NAMESPACE_DNS,
            f"{prefix}:{raw}",
        )