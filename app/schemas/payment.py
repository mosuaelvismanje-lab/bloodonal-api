from pydantic import BaseModel, Field, ConfigDict # ✅ Added ConfigDict
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
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"


# ----------------------------
# Payment Creation (Client → API)
# ----------------------------
class PaymentRequest(BaseModel):
    """
    Used when a user initiates a payment.
    Amount is derived from service unless overridden internally.
    """
    model_config = ConfigDict(from_attributes=True)

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
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool
    reference: str = Field(..., description="Payment reference shown to admin")
    status: PaymentStatus
    expires_at: datetime
    message: Optional[str] = None
    ussd_string: Optional[str] = Field(
        None,
        description="Hidden USSD string for the app to dial"
    )


# ----------------------------
# Free Usage Check Response
# ----------------------------
class FreeUsageResponse(BaseModel):
    """
    Used for checking remaining free usage.
    """
    model_config = ConfigDict(from_attributes=True)

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
    # ✅ Fixed: Changed class Config to model_config
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference: str
    user_id: str
    payer_phone: str
    service_type: str

    amount: float
    currency: str

    provider: str
    provider_tx_id: Optional[str] = None

    status: PaymentStatus
    expires_at: datetime
    confirmed_at: Optional[datetime] = None

    created_at: datetime


class PaymentListResponse(BaseModel):
    """
    Paginated dashboard response.
    """
    model_config = ConfigDict(from_attributes=True)

    total: int
    limit: int
    offset: int
    items: List[PaymentItem]
