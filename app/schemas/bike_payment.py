from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict
from datetime import datetime
# Import your existing Status Enum if possible
from app.schemas.payment import PaymentStatus

class BikePaymentRequest(BaseModel):
    # Matches req.phone in your router
    phone: str = Field(
        ...,
        pattern=r"^\d{9}$",
        description="9-digit mobile money number (e.g., 677123456)"
    )
    metadata: Optional[Dict] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phone": "677123456",
                "metadata": {"source": "mobile_app"}
            }
        }
    )

class BikePaymentResponse(BaseModel):
    success: bool
    reference: str
    status: PaymentStatus  # ✅ Use the Enum for stricter validation
    expires_at: datetime
    message: Optional[str] = None
    ussd_string: Optional[str] = None

class BikeFreeUsageResponse(BaseModel):
    remaining: int