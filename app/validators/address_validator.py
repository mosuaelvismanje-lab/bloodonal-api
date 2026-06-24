# =========================================================
# FILE: app/validators/address_validator.py
# =========================================================

from __future__ import annotations

from typing import Optional


class AddressValidator:
    """
    =========================================================
    ENTERPRISE ADDRESS VALIDATOR
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - Address validation
    - Coordinate validation
    - Country validation
    - Postal code validation
    =========================================================
    """

    # =====================================================
    # ADDRESS LINE
    # =====================================================
    @staticmethod
    def validate_address_line(
        value: Optional[str],
    ) -> str:

        if not value:
            raise ValueError(
                "Address line required"
            )

        value = value.strip()

        if len(value) < 5:
            raise ValueError(
                "Address too short"
            )

        if len(value) > 255:
            raise ValueError(
                "Address too long"
            )

        return value

    # =====================================================
    # CITY
    # =====================================================
    @staticmethod
    def validate_city(
        city: Optional[str],
    ) -> str:

        if not city:
            raise ValueError(
                "City required"
            )

        city = city.strip()

        if len(city) < 2:
            raise ValueError(
                "Invalid city"
            )

        return city

    # =====================================================
    # COUNTRY
    # =====================================================
    @staticmethod
    def validate_country(
        country: Optional[str],
    ) -> str:

        if not country:
            raise ValueError(
                "Country required"
            )

        country = country.strip()

        if len(country) < 2:
            raise ValueError(
                "Invalid country"
            )

        return country

    # =====================================================
    # POSTAL CODE
    # =====================================================
    @staticmethod
    def validate_postal_code(
        postal_code: Optional[str],
    ) -> str:

        if not postal_code:
            return ""

        postal_code = postal_code.strip()

        if len(postal_code) > 20:
            raise ValueError(
                "Postal code too long"
            )

        return postal_code

    # =====================================================
    # LATITUDE
    # =====================================================
    @staticmethod
    def validate_latitude(
        latitude: Optional[float],
    ) -> Optional[float]:

        if latitude is None:
            return None

        if latitude < -90 or latitude > 90:
            raise ValueError(
                "Invalid latitude"
            )

        return latitude

    # =====================================================
    # LONGITUDE
    # =====================================================
    @staticmethod
    def validate_longitude(
        longitude: Optional[float],
    ) -> Optional[float]:

        if longitude is None:
            return None

        if longitude < -180 or longitude > 180:
            raise ValueError(
                "Invalid longitude"
            )

        return longitude

    # =====================================================
    # LABEL
    # =====================================================
    @staticmethod
    def validate_label(
        label: Optional[str],
    ) -> str:

        if not label:
            return "Home"

        label = label.strip()

        allowed = {
            "Home",
            "Work",
            "Office",
            "School",
            "Hospital",
            "Other",
        }

        if label not in allowed:
            return "Other"

        return label