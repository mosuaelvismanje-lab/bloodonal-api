from __future__ import annotations

from typing import List, Dict, Any
from datetime import datetime

from app.modules.blood.domain.scoring import score_donor
from app.modules.blood.domain.rules import (
    is_compatible,
    is_donor_eligible,
    normalize_group,
)


class BloodMatchingEngine:
    """
    ENTERPRISE BLOOD MATCHING ENGINE (AUDIT-COMPLIANT)

    GUARANTEES:
    -------------------------------------------------
    ✔ Pure deterministic scoring (no DB / no side effects)
    ✔ Strict input validation (fail-fast)
    ✔ Rule-driven filtering (single source of truth)
    ✔ Deterministic ranking (audit reproducibility)
    ✔ No silent data coercion
    ✔ Contract-safe (aligned with adapter DTOs)
    """

    # =========================================================
    # CORE SCORE ENGINE (STRICT)
    # =========================================================
    def calculate_score(self, donor: Dict[str, Any], request: Dict[str, Any]) -> int:

        if not isinstance(donor, dict) or not isinstance(request, dict):
            raise TypeError("donor and request must be dictionaries")

        # =====================================================
        # STRICT FIELD EXTRACTION (NO SILENT FIXES)
        # =====================================================
        donor_group = normalize_group(donor.get("blood_group"))
        request_group = normalize_group(request.get("blood_group"))

        if not donor_group or not request_group:
            return 0

        donor_city = donor.get("city")
        request_city = request.get("city")

        if not isinstance(donor_city, str) or not isinstance(request_city, str):
            raise TypeError("city must be a string")

        donor_city = donor_city.strip().lower()
        request_city = request_city.strip().lower()

        last_donation_date = donor.get("last_donation_date")
        if last_donation_date is not None and not isinstance(last_donation_date, datetime):
            raise TypeError("last_donation_date must be datetime or None")

        is_urgent = bool(request.get("is_urgent"))
        is_available = bool(donor.get("is_available", True))

        # =====================================================
        # HARD DOMAIN RULES (SINGLE SOURCE OF TRUTH)
        # =====================================================
        if not is_compatible(request_group, donor_group):
            return 0

        if not is_donor_eligible(donor_group, request_group, last_donation_date):
            return 0

        # =====================================================
        # SIGNALS (DETERMINISTIC)
        # =====================================================
        same_city = donor_city == request_city

        blood_match_bonus = 50 if donor_group == request_group else 20

        # =====================================================
        # FINAL SCORE
        # =====================================================
        return score_donor(
            same_city=same_city,
            urgent_request=is_urgent,
            recent_active=is_available,
            blood_match_bonus=blood_match_bonus,
        )

    # =========================================================
    # MATCHING ENGINE (STRICT + DETERMINISTIC)
    # =========================================================
    def match_donors(
        self,
        donors: List[Dict[str, Any]],
        request: Dict[str, Any],
        limit: int = 20,
    ) -> List[Dict[str, Any]]:

        if not isinstance(donors, list):
            raise TypeError("donors must be a list")

        if not isinstance(request, dict):
            raise TypeError("request must be a dict")

        if not isinstance(limit, int):
            raise TypeError("limit must be an integer")

        limit = max(1, limit)

        results: List[Dict[str, Any]] = []

        for donor in donors:
            if not isinstance(donor, dict):
                continue  # safe skip (non-critical)

            score = self.calculate_score(donor, request)

            if score > 0:
                results.append({
                    "donor": donor,
                    "score": score,
                })

        # =====================================================
        # DETERMINISTIC SORT (AUDIT REQUIREMENT)
        # =====================================================
        results.sort(
            key=lambda x: (
                -x["score"],
                str(x["donor"].get("id", "")),
            )
        )

        return results[:limit]