# =========================================================
# FILE: app/mappers/address_mapper.py
# =========================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.user.user_address import (
    UserAddress,
)


class AddressMapper:
    """
    =========================================================
    ADDRESS MAPPER
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - Convert UserAddress models to API responses
    - Normalize address payloads
    - Prevent schema leakage
    =========================================================
    """

    # =====================================================
    # SINGLE ADDRESS
    # =====================================================
    def to_response(
        self,
        address: Optional[UserAddress],
    ) -> Optional[Dict[str, Any]]:

        if not address:
            return None

        return {
            "id": str(address.id),
            "user_id": str(address.user_id),
            "label": getattr(
                address,
                "label",
                None,
            ),
            "address_line_1": getattr(
                address,
                "address_line_1",
                None,
            ),
            "address_line_2": getattr(
                address,
                "address_line_2",
                None,
            ),
            "city": getattr(
                address,
                "city",
                None,
            ),
            "state": getattr(
                address,
                "state",
                None,
            ),
            "postal_code": getattr(
                address,
                "postal_code",
                None,
            ),
            "country": getattr(
                address,
                "country",
                None,
            ),
            "latitude": getattr(
                address,
                "latitude",
                None,
            ),
            "longitude": getattr(
                address,
                "longitude",
                None,
            ),
            "is_default": getattr(
                address,
                "is_default",
                False,
            ),
            "created_at": (
                address.created_at.isoformat()
                if getattr(
                    address,
                    "created_at",
                    None,
                )
                else None
            ),
            "updated_at": (
                address.updated_at.isoformat()
                if getattr(
                    address,
                    "updated_at",
                    None,
                )
                else None
            ),
        }

    # =====================================================
    # MANY ADDRESSES
    # =====================================================
    def to_response_list(
        self,
        addresses: List[UserAddress],
    ) -> List[Dict[str, Any]]:

        return [
            self.to_response(address)
            for address in addresses
        ]


# =========================================================
# SINGLETON
# =========================================================
address_mapper = AddressMapper()