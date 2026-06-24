# =========================================================
# FILE: app/validators/security_validator.py
# =========================================================

from __future__ import annotations

import re

from fastapi import HTTPException, status


class SecurityValidator:
    """
    Enterprise Security Validator
    """

    PASSWORD_REGEX = re.compile(
        r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d).{8,}$"
    )

    PHONE_REGEX = re.compile(
        r"^\+?[1-9]\d{7,14}$"
    )

    OTP_REGEX = re.compile(
        r"^\d{4,8}$"
    )

    @classmethod
    def validate_password(
        cls,
        password: str,
    ) -> None:

        if not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password required",
            )

        if not cls.PASSWORD_REGEX.match(password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Password must contain uppercase, "
                    "lowercase, number and be 8+ chars"
                ),
            )

    @classmethod
    def validate_phone(
        cls,
        phone: str,
    ) -> None:

        if not cls.PHONE_REGEX.match(phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid phone number",
            )

    @classmethod
    def validate_otp(
        cls,
        otp: str,
    ) -> None:

        if not cls.OTP_REGEX.match(otp):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OTP code",
            )


security_validator = SecurityValidator()