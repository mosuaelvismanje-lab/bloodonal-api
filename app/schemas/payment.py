from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from enum import Enum


# ----------------------------
# Payment Status (API-safe)
# ----------------------------
class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"  # <-- New


# ----------------------------
# Payment Creation (Client → API)
# ----------------------------
class PaymentRequest(BaseModel):
    """
    Used when a user initiates a payment.
    Amount is derived from service unless overridden internally.
    """

    phone: str = Field(
        ...,
        pattern=r"^\d{9}$",
        description="9-digit MTN/Orange mobile money number"
    )

    metadata: Optional[Dict] = Field(
        None,
        description="Extra metadata (device info, USSD hint, etc)"
    )


# ----------------------------
# Payment Creation Response
# ----------------------------
class PaymentResponse(BaseModel):
    """
    Returned immediately after payment initiation.
    Payment is usually PENDING until admin confirms.
    """

    success: bool
    reference: str = Field(..., description="Payment reference shown to admin")
    status: PaymentStatus
    expires_at: datetime
    message: Optional[str] = None
    ussd_string: Optional[str] = Field(
        None, description="Hidden USSD string for the app to dial"
    )


# ----------------------------
# Free Usage Check Response
# ----------------------------
class FreeUsageResponse(BaseModel):
    remaining: int = Field(
        ...,
        description="How many free actions the user can still perform"
    )


# ----------------------------
# Dashboard / Admin Views
# ----------------------------
class PaymentItem(BaseModel):
    """
    Single payment row for admin dashboard.
    """

    id: str
    reference: str
    user_id: str
    payer_phone: str
    service_type: str

    amount: float
    currency: str

    provider: str
    provider_tx_id: Optional[str] = None

    status: PaymentStatus  # <-- now includes AWAITING_VERIFICATION
    expires_at: datetime
    confirmed_at: Optional[datetime] = None

    created_at: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """
    Paginated dashboard response.
    """

    total: int
    limit: int
    offset: int
    items: List[PaymentItem]
