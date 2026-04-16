from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict
from datetime import datetime

class BloodRequestPaymentRequest(BaseModel):
    """
    Schema for initiating a paid blood request transaction.
    Sent from Android to /v1/payments/blood-request
    """
    model_config = ConfigDict(from_attributes=True)

    phone: str = Field(..., description="The MoMo number that will pay")
    blood_type: str = Field(..., description="e.g., O+, AB-")
    needed_units: int = Field(default=1, ge=1)
    hospital_name: Optional[str] = None
    user_id: Optional[str] = None
    session_metadata: Optional[Dict] = None


class BloodRequestPaymentResponseOut(BaseModel):
    """
    ✅ RENAMED: Standardized with 'Out' suffix to resolve ImportErrors.
    Contains instructions for the USSD dialer for the Android App.
    """
    model_config = ConfigDict(from_attributes=True)

    success: bool
    reference: str
    status: str  # e.g., "PENDING", "SUCCESS"
    message: str

    # ✅ The USSD string the Android app will dial (e.g., *126*9*...)
    ussd_string: Optional[str] = None

    # Metadata for the UI
    amount: float = 0.0
    expires_at: Optional[datetime] = None
    transaction_id: Optional[str] = None