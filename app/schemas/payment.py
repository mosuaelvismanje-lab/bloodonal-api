
#app/schemas/payment
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


# ----------------------------
# Payment Status (Standardized)
# ----------------------------
class PaymentStatus(str, Enum):
    PENDING = "PENDING"  # Created, waiting for user to dial
    SUCCESS = "SUCCESS"  # Fully confirmed and quota updated
    FAILED = "FAILED"  # System or provider error
    CANCELLED = "CANCELLED"  # User manually aborted
    REFUNDED = "REFUNDED"  # Money returned to user
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"  # User submitted TxID, waiting for Admin


# ----------------------------
# Payment Request (Android -> API)
# ----------------------------
class PaymentRequest(BaseModel):
    """
    Validation schema for payment initiation.
    Ensures phone numbers are valid before processing.
    """
    model_config = ConfigDict(from_attributes=True)

    phone: str = Field(
        ...,
        pattern=r"^\d{9,13}$",  # Supports 9 digits or international format
        description="Mobile money number (e.g., 670000000)"
    )

    # Optional fields for specific context
    user_id: Optional[str] = None
    service_type: Optional[str] = "blood-request"

    metadata: Optional[Dict] = Field(
        default_factory=dict,
        description="Extra context like device info or hospital name"
    )


# ----------------------------
# NEW: Manual Verification (Android -> API)
# ----------------------------
class PaymentConfirmRequest(BaseModel):
    """
    Schema for manual Transaction ID submission.
    Used when user types the ID from their SMS or it's auto-extracted.
    """
    model_config = ConfigDict(from_attributes=True)

    reference: str = Field(..., description="The internal payment reference")
    transaction_id: str = Field(
        ...,
        min_length=5,
        description="The provider transaction ID from SMS"
    )


# ----------------------------
# Payment Response (API -> Android)
# ----------------------------

class PaymentResponseOut(BaseModel):
    """
    Response returned after a payment is created, confirmed, or status is polled.
    Renamed to PaymentResponseOut to match Android Data Class.
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool
    reference: str = Field(..., description="Internal reference for tracking")
    status: PaymentStatus

    # ✅ UPDATE: Made Optional. The /confirm/ endpoint doesn't need to return this.
    # Prevents Moshi crashes in Android if the field is missing.
    expires_at: Optional[datetime] = None

    message: Optional[str] = None

    # ✅ THE TRIGGER: Android checks this to show the USSD popup
    ussd_string: Optional[str] = Field(
        None,
        description="USSD code for the user to dial"
    )


# ----------------------------
# Quota Response
# ----------------------------
class FreeUsageResponse(BaseModel):
    """
    Used by /remaining endpoint to inform the UI if it should show 'PAY' button.
    Matches Android's RemainingWithFeeResponse.
    """
    model_config = ConfigDict(from_attributes=True)

    remaining: int = Field(..., description="Count of remaining free units")

    # ✅ Standardized: Optional fee (default 0) to match Kotlin default
    fee: Optional[int] = Field(0, description="Cost of the service if remaining is 0")


# ----------------------------
# Admin / History Models
# ----------------------------
class PaymentItem(BaseModel):
    """
    Full view of a payment record for history or admin dashboard.
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None  # Using str for UUID compatibility
    reference: str
    user_id: str
    user_phone: str
    service_type: str

    amount: float
    currency: str = "XAF"

    status: PaymentStatus
    provider: str  # MTN or ORANGE
    provider_tx_id: Optional[str] = None  # The user-submitted ID

    created_at: datetime
    expires_at: datetime
    confirmed_at: Optional[datetime] = None


class PaymentListResponse(BaseModel):
    """
    Standard paginated list response for payment history.
    """
    model_config = ConfigDict(from_attributes=True)

    total: int
    items: List[PaymentItem]
    limit: int = 100
    offset: int = 0


# ----------------------------
# Specialized Service Models
# ----------------------------
class BloodRequestPaymentRequest(PaymentRequest):
    """Specific request for blood services, extending base PaymentRequest."""
    blood_type: str
    needed_units: int
    hospital_name: str
    session_metadata: Optional[Dict] = {}


class BloodRequestPaymentResponse(PaymentResponseOut):
    """Specific response for blood services, extending base PaymentResponseOut."""
    amount: float = 1000.0  # Default fee for blood requests in 2026