from __future__ import annotations

from typing import Dict, Any, Optional
from datetime import datetime

from .contracts import DonorDTO, RequestDTO


class ScoringAdapter:
    """
    ENTERPRISE ADAPTER LAYER (STRICTLY PURE)

    ✔ Only responsibility: type-safe transformation
    ✔ No business rules
    ✔ No defaults that change meaning
    ✔ No hidden constraints
    """

    # =========================================================
    # PUBLIC NORMALIZERS
    # =========================================================
    def normalize_donor(self, d: Any) -> DonorDTO:
        d = self._ensure_dict(d)

        return {
            "city": self._text(d.get("city")),
            "blood_group": self._text(d.get("blood_group")).upper(),
            "is_available": self._bool(d.get("is_available")),

            "successful_responses": self._int(d.get("successful_responses")),
            "rejection_count": self._int(d.get("rejection_count")),

            "avg_response_minutes": self._float(d.get("avg_response_minutes")),
            "fraud_risk_score": self._clamp_0_100(d.get("fraud_risk_score")),

            "last_active": self._datetime(d.get("last_active")),
        }

    def normalize_request(self, r: Any) -> RequestDTO:
        r = self._ensure_dict(r)

        return {
            "city": self._text(r.get("city")),
            "blood_group": self._text(r.get("blood_group")).upper(),

            "is_urgent": self._bool(r.get("is_urgent")),

            "active_donors": self._int(r.get("active_donors")),
            "required_donors": self._int(r.get("required_donors")),

            "hospital_priority_level": self._int(r.get("hospital_priority_level")),
        }

    # =========================================================
    # STRICT TYPE SAFETY
    # =========================================================
    def _ensure_dict(self, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return v
        raise TypeError(f"Expected dict input, got {type(v).__name__}")

    # =========================================================
    # SAFE CASTING (NO BUSINESS LOGIC HERE)
    # =========================================================
    def _text(self, v: Any) -> str:
        return "" if v is None else str(v).strip()

    def _bool(self, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v.strip().lower() in {"true", "1", "yes", "y", "t"}
        return False

    def _int(self, v: Any) -> int:
        try:
            return int(v)
        except Exception:
            return 0

    def _float(self, v: Any) -> float:
        try:
            val = float(v)
            if val != val or val in (float("inf"), float("-inf")):
                return 0.0
            return val
        except Exception:
            return 0.0

    def _clamp_0_100(self, v: Any) -> int:
        try:
            val = int(v)
        except Exception:
            return 0
        return max(0, min(val, 100))

    def _datetime(self, v: Any) -> Optional[datetime]:
        return v if isinstance(v, datetime) else None