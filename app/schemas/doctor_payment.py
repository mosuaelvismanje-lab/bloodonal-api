# app/schemas/doctor_payment.py
from pydantic import BaseModel
from typing import Optional, Dict


class DoctorPaymentRequest(BaseModel):
    user_id: str
    doctor_id: str
    service_type: str  # e.g., "consultation", "follow-up"
    session_metadata: Optional[Dict] = None


class DoctorPaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
