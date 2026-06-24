from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


# =========================================================
# ⚙️ CONFIGURATION (AUDIT-TRACEABLE RULE SET)
# =========================================================
class SurgeConfig:
    MIN_MULTIPLIER = 1.0
    MAX_MULTIPLIER = 5.0

    BASE_URGENT = 1.5
    BASE_NON_URGENT = 1.0

    SHORTAGE_WEIGHT = 1.5
    PRIORITY_STEP = 0.2
    SHORTAGE_SCORE_WEIGHT = 0.3
    UNIT_WEIGHT = 0.1

    MAX_SHORTAGE_BOOST = 1.0
    MAX_UNIT_BOOST = 0.5

    MAX_DONOR_SURGE_BONUS = 5000
    MAX_HOSPITAL_SURGE_FEE = 20000


# =========================================================
# 📦 SURGE CONTEXT (PURE INPUT CONTRACT)
# =========================================================
@dataclass(slots=True)
class SurgeContext:
    is_urgent: bool = False
    request_units: int = 1
    active_donors: int = 0
    required_donors: int = 1

    hospital_priority_level: int = 0
    shortage_score: float = 0.0
    base_amount: int = 0


# =========================================================
# 🧠 SURGE PRICING ENGINE (SINGLE SOURCE OF TRUTH)
# =========================================================
class SurgePricingEngine:
    """
    Enterprise Surge Engine

    Guarantees:
    ✔ deterministic
    ✔ no side effects
    ✔ fully auditable
    ✔ safe bounded math
    """

    def __init__(self, config: SurgeConfig | None = None):
        self.config = config or SurgeConfig()

    # -------------------------------
    # SAFE HELPERS
    # -------------------------------
    def _int(self, v: int) -> int:
        return int(v or 0)

    def _float(self, v: float) -> float:
        return float(v or 0.0)

    # -------------------------------
    # MULTIPLIER CORE
    # -------------------------------
    def get_multiplier(self, ctx: SurgeContext) -> float:

        multiplier = (
            self.config.BASE_URGENT
            if ctx.is_urgent
            else self.config.BASE_NON_URGENT
        )

        # shortage ratio
        required = max(1, self._int(ctx.required_donors))
        active = self._int(ctx.active_donors)

        shortage_ratio = max(0.0, (required - active) / required)
        multiplier += shortage_ratio * self.config.SHORTAGE_WEIGHT

        # hospital priority
        priority = max(0, min(self._int(ctx.hospital_priority_level), 3))
        multiplier += priority * self.config.PRIORITY_STEP

        # shortage score
        multiplier += min(
            self._float(ctx.shortage_score) * self.config.SHORTAGE_SCORE_WEIGHT,
            self.config.MAX_SHORTAGE_BOOST,
        )

        # request units
        units = max(1, self._int(ctx.request_units))
        if units > 1:
            multiplier += min(
                (units - 1) * self.config.UNIT_WEIGHT,
                self.config.MAX_UNIT_BOOST,
            )

        return round(
            max(
                self.config.MIN_MULTIPLIER,
                min(multiplier, self.config.MAX_MULTIPLIER),
            ),
            2,
        )

    # -------------------------------
    # HOSPITAL FEE
    # -------------------------------
    def calculate_hospital_fee(self, ctx: SurgeContext) -> int:

        if ctx.base_amount <= 0:
            return 0

        multiplier = self.get_multiplier(ctx)

        fee = int(ctx.base_amount * (multiplier - 1.0))

        return max(
            0,
            min(fee, self.config.MAX_HOSPITAL_SURGE_FEE),
        )

    # -------------------------------
    # DONOR BONUS
    # -------------------------------
    def calculate_donor_bonus(self, ctx: SurgeContext, base_bonus: int = 0) -> int:

        multiplier = self.get_multiplier(ctx)

        bonus = int(
            base_bonus +
            (ctx.base_amount * (multiplier - 1.0) * 0.5)
        )

        if ctx.is_urgent and ctx.active_donors < ctx.required_donors:
            bonus += 100

        return max(
            0,
            min(bonus, self.config.MAX_DONOR_SURGE_BONUS),
        )

    # -------------------------------
    # FULL AUDIT PAYLOAD
    # -------------------------------
    def build_surge_payload(self, ctx: SurgeContext) -> Dict[str, Any]:

        return {
            "is_urgent": ctx.is_urgent,
            "request_units": ctx.request_units,
            "active_donors": ctx.active_donors,
            "required_donors": ctx.required_donors,
            "hospital_priority_level": ctx.hospital_priority_level,
            "shortage_score": ctx.shortage_score,

            "multiplier": self.get_multiplier(ctx),
            "hospital_fee": self.calculate_hospital_fee(ctx),
            "donor_bonus": self.calculate_donor_bonus(ctx),
        }


# =========================================================
# 🔌 PUBLIC SAFE API (WRAPPERS ONLY)
# =========================================================
def get_surge_multiplier(ctx: SurgeContext) -> float:
    return SurgePricingEngine().get_multiplier(ctx)


def calculate_surge_fee(ctx: SurgeContext) -> int:
    return SurgePricingEngine().calculate_hospital_fee(ctx)


def calculate_surge_bonus(ctx: SurgeContext, base_bonus: int = 0) -> int:
    return SurgePricingEngine().calculate_donor_bonus(ctx, base_bonus)