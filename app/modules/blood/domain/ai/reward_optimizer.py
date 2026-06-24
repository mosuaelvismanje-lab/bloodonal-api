from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from app.modules.blood.domain.ai.surge_pricing import (
    SurgeContext,
    SurgePricingEngine,
    get_surge_multiplier,
)

logger = logging.getLogger(__name__)


# =========================================================
# ⚙️ CONFIG (CENTRALIZED RULES - AUDIT SAFE)
# =========================================================
class RewardConfig:
    MIN_POINTS = 0
    MAX_POINTS = 1000

    BASE_COMPLETION_POINTS = 50
    URGENT_COMPLETION_BONUS = 25
    SAME_CITY_BONUS = 20
    EXACT_MATCH_BONUS = 25

    RESPONSE_BONUS_CAP = 50
    RELIABILITY_BONUS_CAP = 30
    SURGE_BONUS_CAP = 100

    INCENTIVE_CAP = 40
    UNIT_BONUS_CAP = 30
    PRIORITY_BONUS_CAP = 15

    POINT_TO_CREDIT_RATIO = Decimal("1.0")


# =========================================================
# 📦 CONTEXT (IMMUTABLE INPUT CONTRACT)
# =========================================================
@dataclass(slots=True, frozen=True)
class RewardContext:
    is_completed: bool = True
    is_urgent: bool = False
    same_city: bool = False
    exact_blood_match: bool = False

    response_minutes: Optional[int] = None

    donor_points: int = 0
    total_donations: int = 0
    successful_responses: int = 0
    rejection_count: int = 0

    incentive_amount: int = 0

    request_units: int = 1
    hospital_priority_level: int = 0
    active_donors: int = 0
    required_donors: int = 0

    surge_multiplier: Optional[float] = None

    reference_code: Optional[str] = None
    payment_reference: Optional[str] = None

    def __post_init__(self) -> None:
        if self.response_minutes is not None and self.response_minutes < 0:
            raise ValueError("response_minutes cannot be negative")

        if self.donor_points < 0:
            raise ValueError("donor_points cannot be negative")

        if self.total_donations < 0:
            raise ValueError("total_donations cannot be negative")

        if self.successful_responses < 0:
            raise ValueError("successful_responses cannot be negative")

        if self.rejection_count < 0:
            raise ValueError("rejection_count cannot be negative")

        if self.incentive_amount < 0:
            raise ValueError("incentive_amount cannot be negative")

        if self.request_units < 1:
            raise ValueError("request_units must be at least 1")

        if self.hospital_priority_level < 0:
            raise ValueError("hospital_priority_level cannot be negative")

        if self.active_donors < 0:
            raise ValueError("active_donors cannot be negative")

        if self.required_donors < 0:
            raise ValueError("required_donors cannot be negative")

        if self.surge_multiplier is not None and self.surge_multiplier < 1.0:
            raise ValueError("surge_multiplier cannot be less than 1.0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_completed": self.is_completed,
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
            "surge_multiplier": self.surge_multiplier,
            "reference_code": self.reference_code,
            "payment_reference": self.payment_reference,
        }


# =========================================================
# 🧠 REWARD ENGINE (HARDENED)
# =========================================================
class RewardOptimizer:
    """
    ENTERPRISE REWARD ENGINE

    Guarantees:
    -------------------------------------------------
    ✔ deterministic output
    ✔ no silent failure
    ✔ strict caps enforced
    ✔ explicit dependencies
    ✔ audit traceable
    """

    def __init__(self, surge_engine: Optional[SurgePricingEngine] = None):
        self.surge_engine = surge_engine

    # =========================================================
    # MAIN SCORE ENGINE
    # =========================================================
    def calculate_points(self, ctx: RewardContext) -> int:
        if not ctx.is_completed:
            return 0

        points = RewardConfig.BASE_COMPLETION_POINTS

        # -------------------------
        # CORE BONUSES
        # -------------------------
        if ctx.is_urgent:
            points += RewardConfig.URGENT_COMPLETION_BONUS

        if ctx.same_city:
            points += RewardConfig.SAME_CITY_BONUS

        if ctx.exact_blood_match:
            points += RewardConfig.EXACT_MATCH_BONUS

        # -------------------------
        # RESPONSE SPEED
        # -------------------------
        points += min(
            self._response_bonus(ctx.response_minutes),
            RewardConfig.RESPONSE_BONUS_CAP,
        )

        # -------------------------
        # RELIABILITY
        # -------------------------
        points += min(
            self._reliability_bonus(ctx),
            RewardConfig.RELIABILITY_BONUS_CAP,
        )

        # -------------------------
        # INCENTIVES
        # -------------------------
        if ctx.incentive_amount > 0:
            points += min(
                ctx.incentive_amount // 1000,
                RewardConfig.INCENTIVE_CAP,
            )

        # -------------------------
        # SURGE
        # -------------------------
        surge = self._get_surge_multiplier(ctx)
        points += min(
            max(int((surge - 1.0) * 40), 0),
            RewardConfig.SURGE_BONUS_CAP,
        )

        # -------------------------
        # MULTI-UNIT
        # -------------------------
        if ctx.request_units > 1:
            points += min(
                (ctx.request_units - 1) * 10,
                RewardConfig.UNIT_BONUS_CAP,
            )

        # -------------------------
        # PRIORITY
        # -------------------------
        if ctx.hospital_priority_level > 0:
            points += min(
                ctx.hospital_priority_level * 5,
                RewardConfig.PRIORITY_BONUS_CAP,
            )

        final = max(
            RewardConfig.MIN_POINTS,
            min(points, RewardConfig.MAX_POINTS),
        )

        logger.info(
            "reward_calculated ref=%s points=%s",
            ctx.reference_code,
            final,
        )

        return final

    # =========================================================
    # WALLET CREDIT
    # =========================================================
    def calculate_wallet_credit(self, ctx: RewardContext) -> Decimal:
        points = self.calculate_points(ctx)
        return Decimal(points) * RewardConfig.POINT_TO_CREDIT_RATIO

    # =========================================================
    # FULL PAYLOAD
    # =========================================================
    def build_reward_payload(self, ctx: RewardContext) -> Dict[str, Any]:
        points = self.calculate_points(ctx)
        credit = self.calculate_wallet_credit(ctx)
        surge = self._get_surge_multiplier(ctx)

        return {
            "reference_code": ctx.reference_code,
            "payment_reference": ctx.payment_reference,
            "reward_points": points,
            "wallet_credit": str(credit),
            "surge_multiplier": surge,
            "label": self.get_reward_label(points),
            "meta": ctx.to_dict(),
        }

    # =========================================================
    # LABEL ENGINE
    # =========================================================
    def get_reward_label(self, points: int) -> str:
        if points >= 300:
            return "Platinum Hero"
        if points >= 200:
            return "Gold Lifesaver"
        if points >= 100:
            return "Silver Donor"
        if points > 0:
            return "Bronze Donor"
        return "No Reward"

    # =========================================================
    # HELPERS
    # =========================================================
    def _response_bonus(self, minutes: Optional[int]) -> int:
        if minutes is None:
            return 0
        if minutes <= 10:
            return 20
        if minutes <= 30:
            return 10
        if minutes <= 60:
            return 5
        return 0

    def _reliability_bonus(self, ctx: RewardContext) -> int:
        bonus = 0

        bonus += ctx.donor_points // 20
        bonus += min(ctx.total_donations * 2, 10)
        bonus += min(ctx.successful_responses * 2, 15)

        penalty = min(ctx.rejection_count * 5, 20)

        return max(0, bonus - penalty)

    def _get_surge_multiplier(self, ctx: RewardContext) -> float:
        try:
            if ctx.surge_multiplier is not None:
                return max(1.0, float(ctx.surge_multiplier))

            surge_ctx = SurgeContext(
                is_urgent=ctx.is_urgent,
                request_units=ctx.request_units,
                active_donors=ctx.active_donors,
                required_donors=max(ctx.required_donors, ctx.request_units),
                hospital_priority_level=ctx.hospital_priority_level,
                shortage_score=0.0,
                base_amount=ctx.incentive_amount,
            )

            if self.surge_engine is not None:
                # Keep compatibility with an injected engine if your project uses one.
                return max(1.0, float(get_surge_multiplier(surge_ctx)))

            return max(1.0, float(get_surge_multiplier(surge_ctx)))

        except Exception:
            logger.exception("surge_calculation_failed")
            return 1.0


# =========================================================
# PUBLIC API (SAFE WRAPPERS)
# =========================================================
def optimize_reward(ctx: RewardContext, engine: RewardOptimizer) -> Dict[str, Any]:
    return engine.build_reward_payload(ctx)


def calculate_reward_points(ctx: RewardContext, engine: RewardOptimizer) -> int:
    return engine.calculate_points(ctx)


def calculate_wallet_credit(ctx: RewardContext, engine: RewardOptimizer) -> Decimal:
    return engine.calculate_wallet_credit(ctx)