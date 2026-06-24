# =========================================================
# FILE: app/validators/user_validator.py
# =========================================================

from __future__ import annotations

from datetime import date
from typing import Optional


class UserValidator:
    """
    =========================================================
    ENTERPRISE USER VALIDATOR
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - Username validation
    - Name validation
    - Age validation
    - Bio validation
    - Gender validation
    =========================================================
    """

    # =====================================================
    # FULL NAME
    # =====================================================
    @staticmethod
    def validate_full_name(
        value: Optional[str],
    ) -> str:

        if not value:
            raise ValueError(
                "Full name required"
            )

        value = value.strip()

        if len(value) < 2:
            raise ValueError(
                "Full name too short"
            )

        if len(value) > 120:
            raise ValueError(
                "Full name too long"
            )

        return value

    # =====================================================
    # USERNAME
    # =====================================================
    @staticmethod
    def validate_username(
        username: Optional[str],
    ) -> str:

        if not username:
            raise ValueError(
                "Username required"
            )

        username = username.strip().lower()

        if " " in username:
            raise ValueError(
                "Username cannot contain spaces"
            )

        if len(username) < 3:
            raise ValueError(
                "Username too short"
            )

        if len(username) > 30:
            raise ValueError(
                "Username too long"
            )

        return username

    # =====================================================
    # DATE OF BIRTH
    # =====================================================
    @staticmethod
    def validate_date_of_birth(
        dob: Optional[date],
    ) -> date:

        if not dob:
            raise ValueError(
                "Date of birth required"
            )

        today = date.today()

        age = (
            today.year
            - dob.year
            - (
                (today.month, today.day)
                < (dob.month, dob.day)
            )
        )

        if age < 13:
            raise ValueError(
                "Minimum age is 13"
            )

        return dob

    # =====================================================
    # BIO VALIDATION
    # =====================================================
    @staticmethod
    def validate_bio(
        bio: Optional[str],
    ) -> str:

        if not bio:
            return ""

        bio = bio.strip()

        if len(bio) > 500:
            raise ValueError(
                "Bio too long"
            )

        return bio

    # =====================================================
    # GENDER
    # =====================================================
    @staticmethod
    def validate_gender(
        gender: Optional[str],
    ) -> str:

        if not gender:
            return "unspecified"

        gender = gender.strip().lower()

        allowed = {
            "male",
            "female",
            "other",
            "unspecified",
        }

        if gender not in allowed:
            raise ValueError(
                "Invalid gender"
            )

        return gender