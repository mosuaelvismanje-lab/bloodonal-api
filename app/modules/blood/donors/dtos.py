from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


# =========================================================
# DONOR DASHBOARD DTO (CLEAN + BACKWARD COMPATIBLE)
# =========================================================
@dataclass(frozen=True)
class DonorDashboardDTO:
    donor_id: str
    full_name: str
    phone: str

    blood_group: str
    city: str

    is_available: bool
    is_active: bool

    points: int
    rank: str

    wallet_id: Optional[str]

    referral_code: Optional[str]
    referral_count: int
    donation_streak: int

    # -------------------------
    # ACTIVITY METRICS
    # -------------------------
    active_matches: int
    accepted_requests: int
    completed_donations: int
    cancelled_requests: int

    # -------------------------
    # PERFORMANCE METRICS
    # -------------------------
    success_rate: float
    total_lives_helped: int

    # -------------------------
    # EXTRA DONOR STATS
    # -------------------------
    total_donations: int
    successful_responses: int
    rejection_count: int

    # -------------------------
    # TIMELINE / STATUS
    # -------------------------
    last_donation_date: Optional[datetime]
    next_eligible_date: Optional[datetime]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    is_eligible: bool

    # =========================================================
    # FACTORY (ROBUST + BACKWARD COMPATIBLE API CONTRACT)
    # =========================================================
    @staticmethod
    def from_raw(data: Dict[str, Any]) -> "DonorDashboardDTO":
        if not isinstance(data, dict):
            raise TypeError("DonorDashboardDTO.from_raw expects a dict")

        donor_id = _first_str(data, "donor_id", "donorId", "id")
        if not donor_id:
            raise ValueError("donor_id is required")

        return DonorDashboardDTO(
            donor_id=donor_id,
            full_name=_first_str(data, "full_name", "fullName"),
            phone=_first_str(data, "phone", "phone_number", "phoneNumber"),
            blood_group=_first_str(data, "blood_group", "bloodGroup"),
            city=_first_str(data, "city"),
            is_available=_to_bool(
                _first_value(data, "is_available", "isAvailable", default=False)
            ),
            is_active=_to_bool(
                _first_value(data, "is_active", "isActive", default=True)
            ),
            points=_to_int(_first_value(data, "points", default=0)),
            rank=_first_str(data, "rank", "rank_level", default="Bronze"),
            wallet_id=_optional_str(data, "wallet_id", "walletId"),
            referral_code=_optional_str(data, "referral_code", "referralCode"),
            referral_count=_to_int(
                _first_value(data, "referral_count", "referralCount", default=0)
            ),
            donation_streak=_to_int(
                _first_value(data, "donation_streak", "donationStreak", default=0)
            ),
            active_matches=_to_int(
                _first_value(data, "active_matches", "activeMatches", default=0)
            ),
            accepted_requests=_to_int(
                _first_value(data, "accepted_requests", "acceptedRequests", default=0)
            ),
            completed_donations=_to_int(
                _first_value(data, "completed_donations", "completedDonations", default=0)
            ),
            cancelled_requests=_to_int(
                _first_value(data, "cancelled_requests", "cancelledRequests", default=0)
            ),
            success_rate=_to_float(
                _first_value(data, "success_rate", "successRate", default=0.0)
            ),
            total_lives_helped=_to_int(
                _first_value(data, "total_lives_helped", "totalLivesHelped", default=0)
            ),
            total_donations=_to_int(
                _first_value(data, "total_donations", "totalDonations", default=0)
            ),
            successful_responses=_to_int(
                _first_value(
                    data,
                    "successful_responses",
                    "successfulResponses",
                    default=0,
                )
            ),
            rejection_count=_to_int(
                _first_value(data, "rejection_count", "rejectionCount", default=0)
            ),
            last_donation_date=_to_datetime(
                _first_value(data, "last_donation_date", "lastDonationDate", default=None)
            ),
            next_eligible_date=_to_datetime(
                _first_value(data, "next_eligible_date", "nextEligibleDate", default=None)
            ),
            created_at=_to_datetime(_first_value(data, "created_at", "createdAt", default=None)),
            updated_at=_to_datetime(_first_value(data, "updated_at", "updatedAt", default=None)),
            is_eligible=_to_bool(
                _first_value(data, "is_eligible", "isEligible", default=False)
            ),
        )

    # =========================================================
    # UI HELPERS (FRONTEND CONVENIENCE)
    # =========================================================
    @property
    def streak_count(self) -> int:
        return self.donation_streak

    @property
    def display_name(self) -> str:
        name = (self.full_name or "").strip()
        if name:
            return name
        phone = (self.phone or "").strip()
        return phone if phone else "Unknown Donor"

    @property
    def engagement_score(self) -> int:
        """
        Lightweight frontend scoring for ranking animations/cards.
        """
        return (
            self.points * 2
            + self.completed_donations * 5
            + self.active_matches
        )

    # =========================================================
    # SERIALIZATION
    # =========================================================
    def to_raw(self) -> Dict[str, Any]:
        return {
            "donor_id": self.donor_id,
            "full_name": self.full_name,
            "phone": self.phone,
            "blood_group": self.blood_group,
            "city": self.city,
            "is_available": self.is_available,
            "is_active": self.is_active,
            "points": self.points,
            "rank": self.rank,
            "wallet_id": self.wallet_id,
            "referral_code": self.referral_code,
            "referral_count": self.referral_count,
            "donation_streak": self.donation_streak,
            "streak_count": self.donation_streak,
            "active_matches": self.active_matches,
            "accepted_requests": self.accepted_requests,
            "completed_donations": self.completed_donations,
            "cancelled_requests": self.cancelled_requests,
            "success_rate": self.success_rate,
            "total_lives_helped": self.total_lives_helped,
            "total_donations": self.total_donations,
            "successful_responses": self.successful_responses,
            "rejection_count": self.rejection_count,
            "last_donation_date": self.last_donation_date,
            "next_eligible_date": self.next_eligible_date,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_eligible": self.is_eligible,
            "engagement_score": self.engagement_score,
        }

    # =========================================================
    # IMMUTABLE COPY UPDATE
    # =========================================================
    def copy_with(
        self,
        *,
        donor_id: Optional[str] = None,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
        blood_group: Optional[str] = None,
        city: Optional[str] = None,
        is_available: Optional[bool] = None,
        is_active: Optional[bool] = None,
        points: Optional[int] = None,
        rank: Optional[str] = None,
        wallet_id: Optional[str] = None,
        referral_code: Optional[str] = None,
        referral_count: Optional[int] = None,
        donation_streak: Optional[int] = None,
        active_matches: Optional[int] = None,
        accepted_requests: Optional[int] = None,
        completed_donations: Optional[int] = None,
        cancelled_requests: Optional[int] = None,
        success_rate: Optional[float] = None,
        total_lives_helped: Optional[int] = None,
        total_donations: Optional[int] = None,
        successful_responses: Optional[int] = None,
        rejection_count: Optional[int] = None,
        last_donation_date: Optional[datetime] = None,
        next_eligible_date: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        is_eligible: Optional[bool] = None,
    ) -> "DonorDashboardDTO":
        return DonorDashboardDTO(
            donor_id=donor_id or self.donor_id,
            full_name=full_name or self.full_name,
            phone=phone or self.phone,
            blood_group=blood_group or self.blood_group,
            city=city or self.city,
            is_available=is_available if is_available is not None else self.is_available,
            is_active=is_active if is_active is not None else self.is_active,
            points=points if points is not None else self.points,
            rank=rank or self.rank,
            wallet_id=wallet_id if wallet_id is not None else self.wallet_id,
            referral_code=referral_code if referral_code is not None else self.referral_code,
            referral_count=referral_count if referral_count is not None else self.referral_count,
            donation_streak=donation_streak if donation_streak is not None else self.donation_streak,
            active_matches=active_matches if active_matches is not None else self.active_matches,
            accepted_requests=accepted_requests if accepted_requests is not None else self.accepted_requests,
            completed_donations=completed_donations if completed_donations is not None else self.completed_donations,
            cancelled_requests=cancelled_requests if cancelled_requests is not None else self.cancelled_requests,
            success_rate=success_rate if success_rate is not None else self.success_rate,
            total_lives_helped=total_lives_helped if total_lives_helped is not None else self.total_lives_helped,
            total_donations=total_donations if total_donations is not None else self.total_donations,
            successful_responses=successful_responses if successful_responses is not None else self.successful_responses,
            rejection_count=rejection_count if rejection_count is not None else self.rejection_count,
            last_donation_date=last_donation_date if last_donation_date is not None else self.last_donation_date,
            next_eligible_date=next_eligible_date if next_eligible_date is not None else self.next_eligible_date,
            created_at=created_at if created_at is not None else self.created_at,
            updated_at=updated_at if updated_at is not None else self.updated_at,
            is_eligible=is_eligible if is_eligible is not None else self.is_eligible,
        )


# =========================================================
# INTERNAL HELPERS (SAFE PARSING LAYER)
# =========================================================
def _first_value(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def _first_str(data: Dict[str, Any], *keys: str, default: str = "") -> str:
    value = _first_value(data, *keys, default=default)
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _optional_str(data: Dict[str, Any], *keys: str) -> Optional[str]:
    value = _first_value(data, *keys, default=None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return 0


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return 0.0


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y", "on"}


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        # Handles ISO strings like "2026-06-15T21:53:30.173000Z"
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None