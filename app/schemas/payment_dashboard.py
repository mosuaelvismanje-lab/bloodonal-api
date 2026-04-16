#app/schema/payment_dashboard
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List, Optional
from app.models.payment import PaymentStatus


# ----------------------------
# 1. Individual Payment Item
# ----------------------------
class PaymentItem(BaseModel):
    """
    Standardized schema for admin visibility.
    Optimized for Pydantic V2's Rust-based serialization.
    """
    model_config = ConfigDict(
        from_attributes=True,
        # ✅ New for 2026: Strictly enforce attribute checking for ORM performance
        str_strip_whitespace=True
    )

    id: str = Field(..., description="Unique internal payment reference")
    user_id: str
    payer_phone: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")
    amount: float = Field(..., gt=0)
    currency: str = "XAF"
    status: PaymentStatus
    provider: str  # "MTN" / "ORANGE" / "CASH"
    provider_tx_id: Optional[str] = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def ensure_timezone(cls, v: datetime) -> datetime:
        # ✅ 2026 standard: Force UTC for all admin audit logs
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


# ----------------------------
# 2. Paginated Response
# ----------------------------
class PaymentListResponse(BaseModel):
    """
    Standard pagination wrapper for 2026 admin interfaces.
    """
    model_config = ConfigDict(from_attributes=True)

    total: int = Field(..., ge=0)
    limit: int = Field(default=50, le=100)
    offset: int = Field(default=0, ge=0)
    items: List[PaymentItem]


# ----------------------------
# 3. Enhanced Dashboard Summary
# ----------------------------
class DashboardSummary(BaseModel):
    """
    Summary statistics with 2026 bypass and system health tracking.
    """
    model_config = ConfigDict(from_attributes=True)

    # Core Queues
    total_awaiting_verification: int = Field(
        ..., description="Manual review queue size"
    )
    total_pending: int = Field(
        ..., description="Active USSD sessions"
    )

    # ✅ 2026 Update: Track system-automated vs manual throughput
    revenue_today: float = Field(0.0, ge=0)
    success_count_today: int = Field(0, ge=0)

    # NEW: Automated Bypass health metrics
    auto_matched_today: int = Field(
        default=0, description="Count of SMS-autofilled verifications"
    )

    recent_alerts: List[str] = Field(default_factory=list)