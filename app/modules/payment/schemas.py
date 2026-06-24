from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, validator


# =========================================================
# 💳 BASE PAYMENT SCHEMA
# =========================================================
class PaymentBase(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Amount in XAF")
    currency: str = Field(default="XAF", max_length=10)
    phone_number: str = Field(..., min_length=9, max_length=15)
    provider: str = Field(default="MTN_MOMO", description="Payment provider")


# =========================================================
# 🚀 INITIATE PAYMENT (USER REQUEST)
# =========================================================
class PaymentCreate(PaymentBase):
    """
    User initiates payment.

    Backend will:
    - generate reference code (e.g., a356s)
    - store pending payment
    - return instructions to user
    """

    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional client metadata",
    )

    @validator("phone_number")
    def validate_phone(cls, v: str):
        if not v.startswith(("2376", "6")):
            raise ValueError("Invalid Cameroon phone format")
        return v


# =========================================================
# 📲 PAYMENT INIT RESPONSE
# =========================================================
class PaymentInitResponse(BaseModel):
    payment_id: UUID
    reference_code: str
    amount: Decimal
    currency: str
    instructions: str


# =========================================================
# 📩 SMS VERIFICATION INPUT
# =========================================================
class PaymentVerify(BaseModel):
    """
    Used after SMS detection OR manual confirmation.

    System verifies:
    - transaction_id
    - reference_code
    """

    transaction_id: str = Field(..., description="Financial Transaction Id from SMS")
    reference_code: str = Field(..., description="Backend-generated code")
    amount: Optional[Decimal] = None


# =========================================================
# 🔁 PAYMENT STATUS ENUM RESPONSE
# =========================================================
class PaymentStatusResponse(BaseModel):
    payment_id: UUID
    status: str
    message: Optional[str] = None


# =========================================================
# 📄 FULL PAYMENT RESPONSE
# =========================================================
class PaymentResponse(BaseModel):
    id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    phone_number: str
    provider: str

    status: str
    reference_code: str
    transaction_id: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None

    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =========================================================
# 🔍 ADMIN / ANALYTICS FILTER
# =========================================================
class PaymentFilter(BaseModel):
    user_id: Optional[UUID] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# =========================================================
# 📊 PAYMENT ANALYTICS RESPONSE
# =========================================================
class PaymentAnalytics(BaseModel):
    total_revenue: Decimal
    total_transactions: int
    success_rate: float


# =========================================================
# 🚨 FRAUD CHECK INPUT (OPTIONAL API)
# =========================================================
class FraudCheckRequest(BaseModel):
    user_id: UUID
    amount: Decimal
    phone_number: str
    idempotency_key: Optional[str] = None
    provider_tx_id: Optional[str] = None


# =========================================================
# 🚨 FRAUD CHECK RESPONSE
# =========================================================
class FraudCheckResponse(BaseModel):
    is_fraud: bool
    risk_score: float
    reasons: list[str]
    metadata: Dict[str, Any]


# =========================================================
# 🔐 IDEMPOTENCY SUPPORT
# =========================================================
class IdempotentRequest(BaseModel):
    idempotency_key: str = Field(..., description="Unique request key")


# =========================================================
# 💰 MANUAL ADMIN PAYMENT UPDATE
# =========================================================
class PaymentUpdate(BaseModel):
    status: Optional[str] = None
    transaction_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# =========================================================
# 📤 GENERIC RESPONSE
# =========================================================
class MessageResponse(BaseModel):
    message: str