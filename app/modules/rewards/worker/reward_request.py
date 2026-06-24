from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RewardRequest:
    """
    STRICT INPUT CONTRACT FOR REWARD ENGINE

    Enterprise rules:
    - Immutable request object
    - UUID-normalized identifiers
    - Decimal-safe monetary values
    - Explicit optional context for audit / scoring / preview
    - Compatible with router payloads and service layer usage
    """

    # =========================================================
    # REQUIRED
    # =========================================================
    user_id: UUID | str
    wallet_id: UUID | str

    # =========================================================
    # REWARD INPUT
    # =========================================================
    base_amount: Decimal | int | float | str = Decimal("0")

    # =========================================================
    # MATCH CONTEXT
    # =========================================================
    is_urgent: bool = False
    same_city: bool = False
    exact_blood_match: bool = False
    response_minutes: Optional[int] = None

    # =========================================================
    # DONOR STATS
    # =========================================================
    donor_points: int = 0
    total_donations: int = 0
    successful_responses: int = 0
    rejection_count: int = 0

    # =========================================================
    # REQUEST CONTEXT
    # =========================================================
    incentive_amount: Decimal | int | float | str = Decimal("0")
    request_units: int = 1
    hospital_priority_level: int = 0

    # =========================================================
    # OPTIONAL / SYSTEM
    # =========================================================
    reference: Optional[str] = None
    payment_reference: Optional[str] = None
    phone: Optional[str] = None
    active_donors: int = 0
    required_donors: int = 0
    context: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", self._to_uuid(self.user_id, "user_id"))
        object.__setattr__(self, "wallet_id", self._to_uuid(self.wallet_id, "wallet_id"))

        object.__setattr__(
            self,
            "base_amount",
            self._to_decimal(self.base_amount, "base_amount"),
        )
        object.__setattr__(
            self,
            "incentive_amount",
            self._to_decimal(self.incentive_amount, "incentive_amount"),
        )

        object.__setattr__(self, "is_urgent", bool(self.is_urgent))
        object.__setattr__(self, "same_city", bool(self.same_city))
        object.__setattr__(self, "exact_blood_match", bool(self.exact_blood_match))

        object.__setattr__(
            self,
            "response_minutes",
            self._to_optional_int(self.response_minutes, "response_minutes"),
        )

        object.__setattr__(
            self,
            "donor_points",
            self._to_int(self.donor_points, "donor_points", minimum=0),
        )
        object.__setattr__(
            self,
            "total_donations",
            self._to_int(self.total_donations, "total_donations", minimum=0),
        )
        object.__setattr__(
            self,
            "successful_responses",
            self._to_int(self.successful_responses, "successful_responses", minimum=0),
        )
        object.__setattr__(
            self,
            "rejection_count",
            self._to_int(self.rejection_count, "rejection_count", minimum=0),
        )

        object.__setattr__(
            self,
            "request_units",
            self._to_int(self.request_units, "request_units", minimum=1),
        )
        object.__setattr__(
            self,
            "hospital_priority_level",
            self._to_int(self.hospital_priority_level, "hospital_priority_level", minimum=0),
        )
        object.__setattr__(
            self,
            "active_donors",
            self._to_int(self.active_donors, "active_donors", minimum=0),
        )
        object.__setattr__(
            self,
            "required_donors",
            self._to_int(self.required_donors, "required_donors", minimum=0),
        )

        if self.reference is not None:
            ref = str(self.reference).strip()
            object.__setattr__(self, "reference", ref or None)

        if self.payment_reference is not None:
            pay_ref = str(self.payment_reference).strip()
            object.__setattr__(self, "payment_reference", pay_ref or None)

        if self.phone is not None:
            phone = str(self.phone).strip()
            object.__setattr__(self, "phone", phone or None)

        if self.context is not None and not isinstance(self.context, dict):
            raise TypeError("context must be a mapping (dict) when provided")

    @staticmethod
    def _to_uuid(value: UUID | str, field: str) -> UUID:
        if isinstance(value, UUID):
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                raise ValueError(f"{field} cannot be empty")
            try:
                return UUID(text)
            except Exception as exc:
                raise ValueError(f"{field} must be a valid UUID") from exc
        raise TypeError(f"{field} must be a UUID or UUID string")

    @staticmethod
    def _to_decimal(value: Decimal | int | float | str, field: str) -> Decimal:
        try:
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))
        except Exception as exc:
            raise ValueError(f"{field} must be a valid decimal value") from exc

    @staticmethod
    def _to_int(value: Any, field: str, *, minimum: int = 0) -> int:
        try:
            number = int(value)
        except Exception as exc:
            raise ValueError(f"{field} must be an integer") from exc

        if number < minimum:
            raise ValueError(f"{field} must be greater than or equal to {minimum}")
        return number

    @staticmethod
    def _to_optional_int(value: Any, field: str) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except Exception as exc:
            raise ValueError(f"{field} must be an integer") from exc

    def to_context_dict(self) -> Dict[str, Any]:
        """
        Creates a backend-safe reward context payload.
        Useful when sending the request to scoring, analytics, or logs.
        """
        return {
            "is_urgent": self.is_urgent,
            "same_city": self.same_city,
            "exact_blood_match": self.exact_blood_match,
            "response_minutes": self.response_minutes,
            "donor_points": self.donor_points,
            "total_donations": self.total_donations,
            "successful_responses": self.successful_responses,
            "rejection_count": self.rejection_count,
            "incentive_amount": self.incentive_amount,
            "request_units": self.request_units,
            "hospital_priority_level": self.hospital_priority_level,
            "active_donors": self.active_donors,
            "required_donors": self.required_donors,
            **(self.context or {}),
        }