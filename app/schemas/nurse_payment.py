from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict

class NursePaymentRequest(BaseModel):
    """
    Schema for incoming nurse service payment requests.
    Aligned with the unified Payment Pattern (Doctor/Bike).
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    phone: str  # ✅ ADDED: Required for PaymentService.process_payment
    nurse_id: Optional[str] = "NURSE_GENERIC" # ✅ Changed to Optional for flexibility
    service_type: Optional[str] = "home-care"  # "home-care", "first-aid"
    amount: Optional[float] = 0.0             # ✅ ADDED: For schema consistency
    currency: Optional[str] = "XAF"           # ✅ ADDED: For schema consistency
    session_metadata: Optional[Dict] = None

class NursePaymentResponse(BaseModel):
    """
    Standardized response for nurse payment initiation.
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool
    # ✅ Renamed or aliased to support different pattern expectations
    reference: Optional[str] = None
    transaction_id: Optional[str] = None  # ✅ KEPT: To prevent ImportErrors in other files
    status: Optional[str] = "PENDING"
    message: Optional[str] = None