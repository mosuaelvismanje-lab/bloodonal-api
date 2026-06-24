

from datetime import datetime
from typing import Optional, Dict, List
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================
# 📊 COMMON / BASE
# =========================================================
class BaseResponse(BaseModel):
    success: bool = True


# =========================================================
# 💰 REVENUE
# =========================================================
class RevenueMetrics(BaseModel):
    total_revenue: float = Field(..., example=125000.0)
    total_transactions: int = Field(..., example=320)
    average_transaction: float = Field(..., example=390.0)
    period_days: int = Field(..., example=7)


# =========================================================
# 📊 PAYMENT STATUS
# =========================================================
class PaymentStatusBreakdown(BaseModel):
    success: int = 0
    pending: int = 0
    failed: int = 0
    awaiting_verification: int = 0


# =========================================================
# 💸 WALLET FLOW
# =========================================================
class WalletFlow(BaseModel):
    total_credited: float = 0.0
    total_debited: float = 0.0
    net_flow: float = 0.0
    payouts: float = 0.0
    hospital_spend: float = 0.0


# =========================================================
# 🧠 DONOR ANALYTICS
# =========================================================
class DonorActivity(BaseModel):
    user_id: Optional[UUID] = None
    total_requests: int = 0
    total_acceptances: int = 0
    completion_rate: float = 0.0
    last_active: Optional[datetime] = None
    earnings: float = 0.0


# =========================================================
# 🏥 SUBSCRIPTIONS
# =========================================================
class SubscriptionMetrics(BaseModel):
    active_subscriptions: int = 0
    expired_subscriptions: int = 0
    total_revenue: float = 0.0
    tier_breakdown: Dict[str, int] = Field(default_factory=dict)


# =========================================================
# 🤖 AI INSIGHTS
# =========================================================
class AIInsights(BaseModel):
    most_active_region: Optional[str] = None
    peak_hours: List[int] = Field(default_factory=list)
    predicted_donor_availability: float = 0.0
    recommended_reward_multiplier: float = 1.0


# =========================================================
# 📊 DASHBOARD (MASTER)
# =========================================================
class DashboardResponse(BaseModel):
    revenue: RevenueMetrics
    payments: PaymentStatusBreakdown
    wallet: WalletFlow
    donors: DonorActivity
    subscriptions: SubscriptionMetrics
    ai: AIInsights


# =========================================================
# 📈 CUSTOM RANGE METRICS
# =========================================================
class CustomMetricsResponse(BaseModel):
    start: datetime
    end: datetime

    revenue: float
    transactions: int
    active_users: int
    new_users: int


# =========================================================
# 📊 GENERIC KEY-VALUE (FLEXIBLE)
# =========================================================
class GenericMetrics(BaseModel):
    data: Dict[str, float] = Field(default_factory=dict)