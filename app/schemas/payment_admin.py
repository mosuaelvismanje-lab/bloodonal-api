from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime, timezone
from .payment import PaymentStatus

# ---------------------------------------------------------
# 1. ADMIN VERIFICATION REQUEST
# ---------------------------------------------------------
class AdminConfirmPaymentRequest(BaseModel):
    """
    Schema for manual or system-assisted payment verification.
    Supports 10-digit MTIDs and automated matching logic.
    """
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "transaction_id": "2589631470",
                "payer_phone": "237670000000",
                "provider": "MTN",
                "verification_mode": "AUTO_MATCH",
                "amount": 500
            }
        }
    )

    transaction_id: str = Field(..., min_length=5)
    payer_phone: str = Field(..., description="Phone number of the sender")
    provider: str = Field("MTN", pattern="^(MTN|ORANGE|CASH)$")
    amount: float = Field(..., ge=0)
    verification_mode: str = Field("MANUAL", pattern="^(MANUAL|AUTO_MATCH|BYPASS)$")


# ---------------------------------------------------------
# 2. ADMIN ACTION RESPONSE
# ---------------------------------------------------------
class AdminPaymentActionResponse(BaseModel):
    """Returned after an admin or worker confirms/rejects a payment."""
    model_config = ConfigDict(from_attributes=True)

    success: bool
    reference: str
    new_status: PaymentStatus
    action_by: Optional[str] = "SYSTEM_WORKER"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message: Optional[str] = None


# ---------------------------------------------------------
# 3. DETAILED PAYMENT REPORT
# ---------------------------------------------------------
class DetailedPaymentReport(BaseModel):
    """
    Schema for the Admin 'Recent Transactions' table.
    Bridges the Gap: Combines DB data with Registry display names.
    """
    model_config = ConfigDict(from_attributes=True)

    reference: str
    amount: float
    status: PaymentStatus
    # ✅ Mapped from ServiceRegistry in admin.py logic
    service_display_name: str = Field(..., description="Human readable name from Registry")
    user_id: str
    user_phone: Optional[str] = None
    provider: Optional[str] = None
    provider_transaction_id: Optional[str] = None
    created_at: datetime
    verified_at: Optional[datetime] = None


# ---------------------------------------------------------
# 4. DASHBOARD STATISTICS
# ---------------------------------------------------------
class PaymentDashboardSummary(BaseModel):
    """Enhanced stats for the 2026 Admin Dashboard summary tiles."""
    model_config = ConfigDict(from_attributes=True)

    total_awaiting_verification: int = Field(..., description="Manual queue backlog")
    bypass_matches_today: int = Field(0, description="Auto-verified via SMS Extraction")
    total_revenue_today: float = Field(0.0)
    consultation_revenue_total: float = Field(0.0, description="Revenue specifically from Doctor/Nurse calls")
    mtn_volume_today: float = Field(0.0)
    orange_volume_today: float = Field(0.0)
    recent_alerts: List[str] = Field(default_factory=list)


# ---------------------------------------------------------
# 5. LIVE CALL MONITORING (The Fix)
# ---------------------------------------------------------
class ActiveCallReport(BaseModel):
    """
    Schema for the Admin 'Live Monitor' table.
    Tracks ongoing RTC consultations in real-time.
    """
    model_config = ConfigDict(from_attributes=True)

    session_id: str = Field(..., description="The unique session ID")
    caller_id: str = Field(..., description="The patient or user UID")
    callee_id: str = Field(..., description="The doctor or nurse UID")
    service_type: str = Field(..., description="Category: doctor, nurse, etc.")
    duration_current: int = Field(..., description="Elapsed seconds since call start")