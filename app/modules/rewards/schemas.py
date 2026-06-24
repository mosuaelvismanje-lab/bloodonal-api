from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================
# 🎯 REWARD REQUEST
# =========================================================
class RewardRequestSchema(BaseModel):
    user_id: UUID
    wallet_id: UUID
    base_amount: Decimal = Field(..., gt=0)

    reason: str
    reference: str

    # Context for AI + surge + scoring
    context: Optional[Dict[str, Any]] = None


# =========================================================
# 🚀 REWARD RESPONSE
# =========================================================
class RewardResponseSchema(BaseModel):
    status: str
    reference: str
    transaction_id: Optional[UUID] = None

    amount: Optional[Decimal] = None
    wallet_credit: Optional[Decimal] = None

    risk_score: Optional[float] = None
    fraud_flags: Optional[List[str]] = None

    message: Optional[str] = None


# =========================================================
# 📊 REWARD ANALYTICS RESPONSE
# =========================================================
class RewardAnalyticsSchema(BaseModel):
    user_id: Optional[UUID]

    total_rewards: int = 0
    total_credits: Decimal = 0

    avg_reward: Decimal = 0
    success_rate: float = 0

    surge_multiplier: float = 1.0

    last_updated: datetime = Field(default_factory=datetime.utcnow)


# =========================================================
# 🧠 REWARD CONTEXT (CLIENT INPUT)
# =========================================================
class RewardContextSchema(BaseModel):
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