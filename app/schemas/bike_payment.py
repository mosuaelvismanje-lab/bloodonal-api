from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict
from datetime import datetime
# Import your existing Status Enum from the base payment schema
from app.schemas.payment import PaymentStatus

class BikePaymentRequest(BaseModel):
    """
    Schema for incoming bike payment requests.
    Enforces a strict 9-digit format for mobile money numbers.
    """
    # ✅ Combined ORM support and Schema examples into V2 ConfigDict
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "phone": "677123456",
                "metadata": {"source": "mobile_app"}
            }
        }
    )

    phone: str = Field(
        ...,
        pattern=r"^\d{9}$",
        description="9-digit mobile money number (e.g., 677123456)"
    )
    metadata: Optional[Dict] = Field(default_factory=dict)


class BikePaymentResponse(BaseModel):
    """
    Standardized response for bike payment initiation.
    """
    # ✅ Added for Pydantic V2 compliance
    model_config = ConfigDict(from_attributes=True)

    success: bool
    reference: str
    status: PaymentStatus  # Uses the Enum (e.g., PENDING, SUCCESS)
    expires_at: datetime
    message: Optional[str] = None
    ussd_string: Optional[str] = None


class BikeFreeUsageResponse(BaseModel):
    """
    Response for the remaining free rides endpoint.
    """
    # ✅ Added for Pydantic V2 compliance
    model_config = ConfigDict(from_attributes=True)

    remaining: int = Field(
        ...,
        description="Number of free bike rides the user has left"
    )
