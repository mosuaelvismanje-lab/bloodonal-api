# app/schemas/payment.py
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


class PaymentRequest(BaseModel):
    user_id: str = Field(..., description="User making the payment")
    amount: Optional[float] = Field(None, description="Optional amount override")
    metadata: Optional[Dict] = Field(None, description="Extra data for the payment")


class PaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str] = None
    message: Optional[str] = None
    status: Optional[str] = None               # pending, success, failed
    provider_redirect_url: Optional[str] = None  # if using external payment gateway


class FreeUsageResponse(BaseModel):
    remaining: int = Field(..., description="How many free actions the user can still perform")
