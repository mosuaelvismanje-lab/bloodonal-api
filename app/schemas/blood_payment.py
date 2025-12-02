# app/schemas/blood_payment.py
from pydantic import BaseModel
from typing import Optional, Dict


class BloodRequestPaymentRequest(BaseModel):
    user_id: str
    blood_group: str
    quantity_bags: int
    hospital_id: str
    metadata: Optional[Dict] = None


class BloodRequestPaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
