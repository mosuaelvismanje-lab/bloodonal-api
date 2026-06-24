from __future__ import annotations

import inspect
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict, Literal

from app.modules.blood.domain.engine.matching_engine import BloodMatchingEngine
from app.modules.blood.domain.rules import normalize_group
from app.modules.blood.donors.repository import DonorRepository
from app.modules.blood.donors.services.availability_service import AvailabilityService
from app.modules.blood.donors.seed.seed_donors import SeedDonorService

logger = logging.getLogger(__name__)


# =========================================================
# STRICT DTO CONTRACTS (NO Any LEAKAGE)
# =========================================================
class DonorMatchDTO(TypedDict):
    id: str
    full_name: str
    phone: str
    city: str
    blood_group: str
    is_available: bool
    is_active: bool
    fcm_token: Optional[str]
    points: int
    total_donations: int
    successful_responses: int
    rejection_count: int
    rank_level: str
    referral_code: Optional[str]
    referred_by: Optional[str]
    last_donation_date: Optional[datetime]
    is_seed: bool


class RequestMatchDTO(TypedDict):
    id: str
    city: str
    blood_group: str
    is_urgent: bool
    created_at: Optional[datetime]
    incentive_amount: int
    hospital_location: Optional[str]
    needed_units: Optional[int]
    patient_name: Optional[str]


PriorityLevel = Literal["HIGH", "MEDIUM", "LOW"]
MatchType = Literal["EXACT", "COMPATIBLE"]


# =========================================================
# ADAPTER (AUDIT HARDENED)
# =========================================================
class BloodMatchingAdapter:
    MIN_REAL_DONORS = 5
    DEFAULT_SEED_COUNT = 10
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100

    def __init__(
        self,
        engine: Optional[BloodMatchingEngine] = None,
        donor_repo: Optional[DonorRepository] = None,
        availability: Optional[AvailabilityService] = None,
        seed_service: Optional[SeedDonorService] = None,
    ) -> None:
        self.engine = engine or BloodMatchingEngine()
        self.donor_repo = donor_repo or DonorRepository()
        self.availability = availability or AvailabilityService()
        self.seed_service = seed_service or SeedDonorService()

    # =========================================================
    # MAIN ENTRY (STRICT FAIL-FAST)
    # =========================================================
    async def get_matches(
        self,
        db: Any,
        blood_request: Any,
        limit: int = DEFAULT_LIMIT,
    ) -> List[Dict[str, Any]]:
        if blood_request is None:
            raise ValueError("blood_request cannot be None")

        limit = self._normalize_limit(limit)
        request = self._normalize_request(blood_request)

        if not request["city"] or not request["blood_group"]:
            raise ValueError("Invalid normalized request data")

        donors = await self._maybe_await(
            self.donor_repo.get_active_donors(
                db=db,
                city=request["city"],
                blood_group=request["blood_group"],
            )
        )
        donors = donors or []

        real_donors: List[DonorMatchDTO] = []

        for donor in donors:
            try:
                eligible = await self._maybe_await(
                    self.availability.is_eligible(donor)
                )
                if not eligible:
                    continue
            except Exception:
                logger.exception(
                    "donor_eligibility_check_failed",
                    extra={"donor_id": str(getattr(donor, "id", ""))},
                )
                continue

            real_donors.append(self._normalize_donor(donor, is_seed=False))

        # SEED FALLBACK
        if len(real_donors) < self.MIN_REAL_DONORS:
            seed_donors = await self._maybe_await(
                self.seed_service.generate_seed_donors(
                    city=request["city"],
                    blood_group=request["blood_group"],
                    count=self.DEFAULT_SEED_COUNT,
                )
            )
            seed_donors = seed_donors or []

            for donor in seed_donors:
                real_donors.append(self._normalize_donor(donor, is_seed=True))

        if not real_donors:
            return []

        matches = await self._maybe_await(
            self.engine.match_donors(
                donors=real_donors,
                request=request,
                limit=limit,
            )
        )

        if not isinstance(matches, list):
            raise TypeError("Engine returned invalid response type")

        return self._enrich_matches(matches, request)[:limit]

    # =========================================================
    # REQUEST NORMALIZATION
    # =========================================================
    def _normalize_request(self, blood_request: Any) -> RequestMatchDTO:
        """
        Accepts dict-like objects or ORM objects and returns a strict DTO.
        """
        def pick(*keys: str, default: Any = None) -> Any:
            for key in keys:
                if isinstance(blood_request, dict):
                    if key in blood_request and blood_request[key] is not None:
                        return blood_request[key]
                else:
                    value = getattr(blood_request, key, None)
                    if value is not None:
                        return value
            return default

        request_id = pick("id", "request_id")
        city = pick("city")
        blood_group = pick("blood_group", "bloodGroup")
        is_urgent = pick("is_urgent", "isUrgent", default=False)
        created_at = pick("created_at", "createdAt")
        incentive_amount = pick("incentive_amount", "incentiveAmount", default=0)
        hospital_location = pick("hospital_location", "hospitalLocation")
        needed_units = pick("needed_units", "neededUnits")
        patient_name = pick("patient_name", "patientName")

        normalized_city = self._normalize_city(city)
        normalized_group = self._normalize_blood_group(blood_group)

        if not normalized_city:
            raise ValueError("request.city cannot be empty")

        if not normalized_group:
            raise ValueError("request.blood_group cannot be empty")

        return RequestMatchDTO(
            id=str(request_id) if request_id is not None else "",
            city=normalized_city,
            blood_group=normalized_group,
            is_urgent=self._safe_bool(is_urgent),
            created_at=self._safe_datetime(created_at),
            incentive_amount=self._safe_int(incentive_amount),
            hospital_location=self._safe_optional_str(hospital_location),
            needed_units=self._safe_optional_int(needed_units),
            patient_name=self._safe_optional_str(patient_name),
        )

    # =========================================================
    # DONOR NORMALIZATION
    # =========================================================
    def _normalize_donor(self, donor: Any, *, is_seed: bool) -> DonorMatchDTO:
        """
        Accepts ORM donor objects or dict donors and converts them to a strict DTO.
        """
        def pick(*keys: str, default: Any = None) -> Any:
            for key in keys:
                if isinstance(donor, dict):
                    if key in donor and donor[key] is not None:
                        return donor[key]
                else:
                    value = getattr(donor, key, None)
                    if value is not None:
                        return value
            return default

        donor_id = pick("id")
        blood_group = pick("blood_group", "bloodGroup")
        city = pick("city")

        normalized_group = self._normalize_blood_group(blood_group) or ""
        normalized_city = self._normalize_city(city) or ""

        return DonorMatchDTO(
            id=str(donor_id) if donor_id is not None else "",
            full_name=self._safe_str(pick("full_name", "fullName")),
            phone=self._safe_str(pick("phone")),
            city=normalized_city,
            blood_group=normalized_group,
            is_available=self._safe_bool(pick("is_available", default=False)),
            is_active=self._safe_bool(pick("is_active", default=True)),
            fcm_token=self._safe_optional_str(pick("fcm_token")),
            points=self._safe_int(pick("points", default=0)),
            total_donations=self._safe_int(pick("total_donations", default=0)),
            successful_responses=self._safe_int(
                pick("successful_responses", default=0)
            ),
            rejection_count=self._safe_int(pick("rejection_count", default=0)),
            rank_level=self._safe_str(pick("rank_level", default="Bronze")) or "Bronze",
            referral_code=self._safe_optional_str(pick("referral_code")),
            referred_by=self._safe_optional_str(pick("referred_by")),
            last_donation_date=self._safe_datetime(pick("last_donation_date")),
            is_seed=bool(is_seed),
        )

    # =========================================================
    # ENRICHMENT (FULLY SAFE)
    # =========================================================
    def _enrich_matches(
        self,
        matches: List[Dict[str, Any]],
        request: RequestMatchDTO,
    ) -> List[Dict[str, Any]]:
        enriched: List[Dict[str, Any]] = []

        for item in matches:
            if not isinstance(item, dict):
                continue

            donor = item.get("donor")
            if not isinstance(donor, dict):
                continue

            score = self._safe_int(item.get("score"))

            enriched.append({
                "donor": donor,
                "score": score,
                "priority": self._priority(score),
                "match_type": self._match_type(donor, request),
                "is_emergency_boosted": self._emergency(request, score),
                "audit": {
                    "seed": bool(donor.get("is_seed")),
                    "band": self._score_band(score),
                },
            })

        return sorted(
            enriched,
            key=lambda x: (
                -self._safe_int(x.get("score")),
                str((x.get("donor") or {}).get("id", "")),
            ),
        )

    # =========================================================
    # BUSINESS RULES
    # =========================================================
    def _priority(self, score: int) -> PriorityLevel:
        if score >= 120:
            return "HIGH"
        if score >= 80:
            return "MEDIUM"
        return "LOW"

    def _score_band(self, score: int) -> str:
        if score >= 120:
            return "A"
        if score >= 80:
            return "B"
        return "C"

    def _match_type(
        self,
        donor: Dict[str, Any],
        request: RequestMatchDTO,
    ) -> MatchType:
        return (
            "EXACT"
            if donor.get("blood_group") == request["blood_group"]
            else "COMPATIBLE"
        )

    def _emergency(self, request: RequestMatchDTO, score: int) -> bool:
        return request["is_urgent"] and score >= 80

    # =========================================================
    # SAFE HELPERS
    # =========================================================
    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except Exception:
            return 0

    def _safe_optional_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except Exception:
            return None

    def _safe_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if value is None:
            return False
        return str(value).strip().lower() in {"true", "1", "yes", "y", "on"}

    def _safe_str(self, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _safe_optional_str(self, value: Any) -> Optional[str]:
        text = self._safe_str(value)
        return text or None

    def _safe_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            text = str(value).strip()
            return datetime.fromisoformat(text)
        except Exception:
            return None

    def _normalize_limit(self, limit: int) -> int:
        if not isinstance(limit, int):
            raise TypeError("limit must be an integer")
        return max(1, min(limit, self.MAX_LIMIT))

    def _normalize_city(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text.lower() or None

    def _normalize_blood_group(self, value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None

        # Use your domain normalizer first, then fall back safely
        try:
            normalized = normalize_group(text)
            if normalized:
                return str(normalized).upper()
        except Exception:
            pass

        return text.upper()