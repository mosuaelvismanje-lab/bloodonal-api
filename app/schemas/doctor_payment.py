from pydantic import BaseModel, ConfigDict # ✅ Added ConfigDict
from typing import Optional, Dict


class DoctorPaymentRequest(BaseModel):
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    doctor_id: str
    service_type: str  # e.g., "consultation", "follow-up"
    session_metadata: Optional[Dict] = None


class DoctorPaymentResponse(BaseModel):
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
