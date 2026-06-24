from typing import Optional
from typing import Optional, Any
from datetime import datetime, timezone
import math


# =========================================================
# 🔐 CENTRALIZED SCORING POLICY (AUDIT SAFE)
# =========================================================
class ScoringPolicy:
    CITY_BONUS = 50
    URGENT_BONUS = 35
    RECENT_ACTIVE_BONUS = 20

    INCENTIVE_DIVISOR = 1000
    INCENTIVE_CAP = 40

    POINTS_DIVISOR = 10
    POINTS_CAP = 30

    DONATIONS_MULTIPLIER = 2
    DONATIONS_CAP = 20

    SUCCESS_MULTIPLIER = 3
    SUCCESS_CAP = 25

    REJECTION_MULTIPLIER = 6
    REJECTION_CAP = 40

    DISTANCE_NEAR = 30
    DISTANCE_MEDIUM = 20
    DISTANCE_FAR = 10
    DISTANCE_PENALTY_CAP = 20

    FRESH_DONATION_PENALTY_DAYS = 90
    OLD_DONATION_BONUS_DAYS = 365
    OLD_DONATION_BONUS = 10


# =========================================================
# 🚀 PURE SCORING FUNCTION (AUDIT COMPLIANT)
# =========================================================
def score_donor(
    *,
    same_city: bool,
    urgent_request: bool,
    recent_active: bool,
    blood_match_bonus: int = 0,

    incentive_amount: Optional[float] = None,
    donor_points: int = 0,
    rejection_count: int = 0,
    referral_bonus: int = 0,

    distance_km: Optional[float] = None,
    last_donation_date: Optional[datetime] = None,
    total_donations: int = 0,
    successful_responses: int = 0,
) -> int:

    score = 0

    # =========================================================
    # CORE MATCH SIGNALS
    # =========================================================
    if same_city:
        score += ScoringPolicy.CITY_BONUS

    if urgent_request:
        score += ScoringPolicy.URGENT_BONUS

    if recent_active:
        score += ScoringPolicy.RECENT_ACTIVE_BONUS

    score += _safe_int(blood_match_bonus)

    # =========================================================
    # INCENTIVE SIGNAL (SAFE NORMALIZATION)
    # =========================================================
    if incentive_amount is not None:
        try:
            inc = float(incentive_amount)
            if not math.isnan(inc) and not math.isinf(inc):
                score += min(int(inc / ScoringPolicy.INCENTIVE_DIVISOR),
                             ScoringPolicy.INCENTIVE_CAP)
        except Exception:
            pass

    # =========================================================
    # REPUTATION SIGNALS
    # =========================================================
    score += min(_safe_int(donor_points) // ScoringPolicy.POINTS_DIVISOR,
                 ScoringPolicy.POINTS_CAP)

    score += min(_safe_int(total_donations) * ScoringPolicy.DONATIONS_MULTIPLIER,
                 ScoringPolicy.DONATIONS_CAP)

    score += min(_safe_int(successful_responses) * ScoringPolicy.SUCCESS_MULTIPLIER,
                 ScoringPolicy.SUCCESS_CAP)

    # =========================================================
    # PENALTIES
    # =========================================================
    score -= min(_safe_int(rejection_count) * ScoringPolicy.REJECTION_MULTIPLIER,
                 ScoringPolicy.REJECTION_CAP)

    # =========================================================
    # DISTANCE SIGNAL
    # =========================================================
    if distance_km is not None:
        try:
            d = float(distance_km)
            if math.isnan(d) or math.isinf(d):
                d = None

            if d is not None:
                if d <= 2:
                    score += ScoringPolicy.DISTANCE_NEAR
                elif d <= 5:
                    score += ScoringPolicy.DISTANCE_MEDIUM
                elif d <= 10:
                    score += ScoringPolicy.DISTANCE_FAR
                else:
                    score -= min(int(d), ScoringPolicy.DISTANCE_PENALTY_CAP)
        except Exception:
            pass

    # =========================================================
    # MEDICAL SAFETY SIGNAL (TIMEZONE SAFE)
    # =========================================================
    if last_donation_date is not None:
        try:
            now = datetime.now(timezone.utc)

            if last_donation_date.tzinfo is None:
                last_donation_date = last_donation_date.replace(tzinfo=timezone.utc)

            days_since = (now - last_donation_date).days

            if days_since < ScoringPolicy.FRESH_DONATION_PENALTY_DAYS:
                score -= 50

            elif days_since > ScoringPolicy.OLD_DONATION_BONUS_DAYS:
                score += ScoringPolicy.OLD_DONATION_BONUS

        except Exception:
            pass

    # =========================================================
    # REFERRAL GROWTH SIGNAL
    # =========================================================
    score += _safe_int(referral_bonus)

    # =========================================================
    # FINAL SAFETY BOUNDARY
    # =========================================================
    if math.isnan(score) or math.isinf(score):
        return 0

    return max(int(score), 0)


# =========================================================
# 🛡 SAFE CAST HELPER
# =========================================================
def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0