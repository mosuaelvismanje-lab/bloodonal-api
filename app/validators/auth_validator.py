# =========================================================
# FILE: app/validators/auth_validator.py
# =========================================================

from __future__ import annotations

import re
from typing import Optional


class AuthValidator:
    """
    =========================================================
    ENTERPRISE AUTH VALIDATOR
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - Email validation
    - Password strength validation
    - OTP validation
    - Phone validation
    - Token validation
    =========================================================
    """

    EMAIL_REGEX = re.compile(
        r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    )

    PHONE_REGEX = re.compile(
        r"^\+?[0-9]{8,15}$"
    )

    # =====================================================
    # EMAIL VALIDATION
    # =====================================================
    @staticmethod
    def validate_email(
        email: Optional[str],
    ) -> str:

        if not email:
            raise ValueError(
                "Email is required"
            )

        email = email.strip().lower()

        if not AuthValidator.EMAIL_REGEX.match(
            email
        ):
            raise ValueError(
                "Invalid email format"
            )

        return email

    # =====================================================
    # PASSWORD VALIDATION
    # =====================================================
    @staticmethod
    def validate_password(
        password: Optional[str],
    ) -> str:

        if not password:
            raise ValueError(
                "Password is required"
            )

        password = password.strip()

        if len(password) < 8:
            raise ValueError(
                "Password must be at least 8 characters"
            )

        if not re.search(r"[A-Z]", password):
            raise ValueError(
                "Password must contain uppercase letter"
            )

        if not re.search(r"[a-z]", password):
            raise ValueError(
                "Password must contain lowercase letter"
            )

        if not re.search(r"\d", password):
            raise ValueError(
                "Password must contain number"
            )

        return password

    # =====================================================
    # PHONE VALIDATION
    # =====================================================
    @staticmethod
    def validate_phone(
        phone: Optional[str],
    ) -> str:

        if not phone:
            raise ValueError(
                "Phone number required"
            )

        phone = phone.strip()

        if not AuthValidator.PHONE_REGEX.match(
            phone
        ):
            raise ValueError(
                "Invalid phone number"
            )

        return phone

    # =====================================================
    # OTP VALIDATION
    # =====================================================
    @staticmethod
    def validate_otp(
        otp: Optional[str],
    ) -> str:

        if not otp:
            raise ValueError(
                "OTP required"
            )

        otp = otp.strip()

        if not otp.isdigit():
            raise ValueError(
                "OTP must be numeric"
            )

        if len(otp) not in (4, 6):
            raise ValueError(
                "Invalid OTP length"
            )

        return otp