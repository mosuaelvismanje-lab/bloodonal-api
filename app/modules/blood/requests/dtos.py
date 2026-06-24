from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Any, Dict
from datetime import datetime


# =========================================================
# REQUEST DTO (CREATE)
# =========================================================
@dataclass(frozen=True)
class BloodRequestCreateDTO:
    patient_name: str
    phone: str
    city: str
    blood_group: str
    hospital_location: str
    needed_units: int
    is_urgent: bool
    offer: Optional[str]
    user_id: Any
    expires_at: datetime


# =========================================================
# RESPONSE DTO (CORE ENTITY)
# =========================================================
@dataclass(frozen=True)
class BloodRequestDTO:
    id: str
    patient_name: str
    phone: str
    city: str
    blood_group: str
    hospital_location: str
    needed_units: int
    is_urgent: bool
    offer: Optional[str]
    status: str
    accepted_by: Optional[str]
    created_at: Optional[datetime]
    expires_at: Optional[datetime]

    @staticmethod
    def from_model(model: Any) -> "BloodRequestDTO":
        return BloodRequestDTO(
            id=str(model.id),
            patient_name=model.patient_name,
            phone=model.phone,
            city=model.city,
            blood_group=model.blood_group,
            hospital_location=model.hospital_location,
            needed_units=model.needed_units,
            is_urgent=bool(model.is_urgent),
            offer=model.offer,
            status=model.status,
            accepted_by=getattr(model, "accepted_by", None),
            created_at=getattr(model, "created_at", None),
            expires_at=getattr(model, "expires_at", None),
        )


# =========================================================
# DONOR DASHBOARD DTO
# FULLY MATCHES FLUTTER DonorDashboardModel
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

    active_matches: int
    accepted_requests: int
    completed_donations: int
    cancelled_requests: int

    success_rate: float
    total_lives_helped: int

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # =====================================================
    # SAFE FACTORY FROM RAW QUERY/MAP
    # =====================================================
    @staticmethod
    def from_raw(data: Dict[str, Any]) -> "DonorDashboardDTO":
        return DonorDashboardDTO(
            donor_id=str(data.get("donor_id", "")),

            full_name=str(
                data.get("full_name")
                or data.get("name")
                or ""
            ),

            phone=str(data.get("phone", "")),
            blood_group=str(data.get("blood_group", "")),
            city=str(data.get("city", "")),

            is_available=bool(data.get("is_available", False)),
            is_active=bool(data.get("is_active", True)),

            points=int(data.get("points", 0)),
            rank=str(data.get("rank", "Bronze")),

            wallet_id=(
                str(data["wallet_id"])
                if data.get("wallet_id") is not None
                else None
            ),

            referral_code=(
                str(data["referral_code"])
                if data.get("referral_code") is not None
                else None
            ),

            referral_count=int(data.get("referral_count", 0)),
            donation_streak=int(data.get("donation_streak", 0)),

            active_matches=int(
                data.get("active_matches")
                or data.get("active_requests", 0)
            ),

            accepted_requests=int(
                data.get("accepted_requests", 0)
            ),

            completed_donations=int(
                data.get("completed_donations")
                or data.get("completed_requests", 0)
            ),

            cancelled_requests=int(
                data.get("cancelled_requests", 0)
            ),

            success_rate=float(data.get("success_rate", 0.0)),

            total_lives_helped=int(
                data.get("total_lives_helped", 0)
            ),

            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    # =====================================================
    # SERIALIZER
    # =====================================================
    def to_dict(self) -> Dict[str, Any]:
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

            "active_matches": self.active_matches,
            "accepted_requests": self.accepted_requests,
            "completed_donations": self.completed_donations,
            "cancelled_requests": self.cancelled_requests,

            "success_rate": self.success_rate,
            "total_lives_helped": self.total_lives_helped,

            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),

            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            ),
        }