# app/schemas/nurse_payment.py
from pydantic import BaseModel
from typing import Optional, Dict


class NursePaymentRequest(BaseModel):
    user_id: str
    nurse_id: str
    service_type: str  # "home-care", "first-aid"
    metadata: Optional[Dict] = None


class NursePaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
