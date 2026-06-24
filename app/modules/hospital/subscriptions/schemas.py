

from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field


# =========================================================
# 🏥 PLAN SCHEMAS
# =========================================================
class SubscriptionPlanBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = Field(None, max_length=255)
    price: float = Field(..., ge=0)
    currency: str = Field(default="XAF", min_length=2, max_length=10)
    duration_days: int = Field(..., ge=1)
    priority_multiplier: float = Field(default=1.0, ge=1.0)
    features: Optional[Dict[str, Any]] = None


class SubscriptionPlanCreate(SubscriptionPlanBase):
    pass


class SubscriptionPlanOut(SubscriptionPlanBase):
    id: UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# =========================================================
# 🏥 SUBSCRIPTION SCHEMAS
# =========================================================
class SubscriptionCreateRequest(BaseModel):
    """
    Used when hospital subscribes to a plan.
    """

    plan_id: UUID
    auto_renew: bool = False

    # 🔑 Payment integration (your system)
    idempotency_key: Optional[str] = Field(
        None,
        description="Prevents duplicate payments"
    )


class SubscriptionResponse(BaseModel):
    """
    Returned after creating or fetching a subscription.
    """

    id: UUID
    hospital_id: UUID
    plan_id: UUID

    status: str
    start_date: datetime
    end_date: datetime

    auto_renew: bool
    payment_reference: Optional[str]

    created_at: datetime

    model_config = {"from_attributes": True}


# =========================================================
# 💳 BILLING SCHEMAS
# =========================================================
class SubscriptionBillingOut(BaseModel):
    id: UUID
    hospital_id: UUID
    subscription_id: UUID

    amount: float
    currency: str

    status: str
    provider_reference: Optional[str]

    created_at: datetime

    model_config = {"from_attributes": True}


# =========================================================
# 📊 EXTENDED RESPONSE (WITH PLAN DETAILS)
# =========================================================
class SubscriptionWithPlanResponse(BaseModel):
    """
    Rich response used in dashboards / mobile apps.
    """

    id: UUID
    hospital_id: UUID
    status: str

    start_date: datetime
    end_date: datetime

    auto_renew: bool

    # 🔥 Embedded plan info
    plan: SubscriptionPlanOut

    model_config = {"from_attributes": True}


# =========================================================
# 🔄 ACTION REQUESTS
# =========================================================
class CancelSubscriptionRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=255)


class RenewSubscriptionRequest(BaseModel):
    auto_renew: Optional[bool] = True


# =========================================================
# 📡 API RESPONSE WRAPPERS (CONSISTENT STRUCTURE)
# =========================================================
class SuccessResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class SubscriptionCreateResponse(BaseModel):
    """
    Used after subscription initiation (with payment).
    """

    success: bool = True

    subscription_id: UUID
    status: str

    # 💳 Payment flow
    payment_reference: Optional[str]
    payment_status: Optional[str]

    # 📱 Mobile Money UX
    ussd_string: Optional[str]

    expires_at: Optional[datetime]


class SubscriptionListResponse(BaseModel):
    success: bool = True
    data: list[SubscriptionResponse]