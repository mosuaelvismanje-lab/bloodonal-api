from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional
from datetime import datetime


# ---------------------------------------------------------
# 1. Component Health (Internal System Status)
# ---------------------------------------------------------

class ComponentStatus(BaseModel):
    """Represents the health of an individual system component."""
    status: str = Field(..., example="healthy")
    latency_ms: float = Field(..., example=12.5)
    message: Optional[str] = None


class SystemHealthResponse(BaseModel):
    """Full health check report for the platform."""
    timestamp: datetime
    environment: str
    version: str
    database: ComponentStatus
    redis: ComponentStatus
    firebase: ComponentStatus


# ---------------------------------------------------------
# 2. Performance Metrics (For Dashboard Charts)
# ---------------------------------------------------------

class CallSuccessMetrics(BaseModel):
    """Aggregated stats for RTC sessions."""
    total_initiated: int
    total_completed: int
    total_missed: int
    total_rejected: int
    success_rate: float = Field(..., description="Percentage of initiated calls that were completed")
    avg_duration_seconds: float


class RevenueBreakdown(BaseModel):
    """Financial stats for the admin revenue tile."""
    consultation_total: float = Field(..., alias="consultationRevenue")
    blood_request_total: float = Field(..., alias="bloodRevenue")
    transport_total: float = Field(..., alias="transportRevenue")
    currency: str = "XAF"


# ---------------------------------------------------------
# 3. The Unified Dashboard Contract
# ---------------------------------------------------------

class DashboardMetricsResponse(BaseModel):
    """
    The master schema for the Admin Dashboard.
    Matches the requirements of the Kotlin 'DashboardState' class.
    """
    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    # Summary Tiles
    total_revenue_24h: float = Field(..., alias="dailyRevenue")
    active_users_count: int = Field(..., alias="liveUsers")
    pending_verifications: int = Field(..., alias="waitingBypass")

    # Nested Detailed Data
    revenue_breakdown: RevenueBreakdown
    call_stats: CallSuccessMetrics

    # System Status
    server_uptime_seconds: int
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MetricSeries(BaseModel):
    """Used for generating Line Charts (e.g., Revenue over the last 7 days)."""
    label: str  # e.g., "2026-02-27"
    value: float