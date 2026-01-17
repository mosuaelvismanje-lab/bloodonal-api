# app/schemas/nurse_payment.py
from pydantic import BaseModel, ConfigDict # ✅ Added ConfigDict
from typing import Optional, Dict


class NursePaymentRequest(BaseModel):
    """
    Schema for incoming nurse service payment requests.
    """
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    nurse_id: str
    service_type: str  # "home-care", "first-aid"
    session_metadata: Optional[Dict] = None


class NursePaymentResponse(BaseModel):
    """
    Standardized response for nurse payment initiation.
    """
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
