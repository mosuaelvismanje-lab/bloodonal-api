# app/schemas/blood_payment.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict


class BloodRequestPaymentRequest(BaseModel):
    # ✅ Added ConfigDict for consistency
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    blood_group: str
    quantity_bags: int
    hospital_id: str
    session_metadata: Optional[Dict] = None


class BloodRequestPaymentResponse(BaseModel):
    # ✅ Added ConfigDict for consistency
    model_config = ConfigDict(from_attributes=True)

    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
