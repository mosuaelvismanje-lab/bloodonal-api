from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict
from datetime import datetime
# ✅ Standardized Import: Matches the 142-line payment.py update
from app.schemas.payment import PaymentStatus, PaymentResponseOut


class BikePaymentRequest(BaseModel):
    """
    Schema for incoming bike payment requests.
    Enforces a strict 9-digit format for Cameroon mobile money numbers (MTN/Orange).
    """
    # ✅ Pydantic V2 ConfigDict: Combined ORM and Swagger examples
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "phone": "677123456",
                "metadata": {"bike_type": "standard", "location": "Limbe"}
            }
        }
    )

    phone: str = Field(
        ...,
        pattern=r"^\d{9}$",
        description="9-digit mobile money number (e.g., 677123456)"
    )
    metadata: Optional[Dict] = Field(default_factory=dict)


class BikePaymentResponse(PaymentResponseOut):
    """
    Standardized response for bike payment initiation.
    Inherits from PaymentResponseOut to resolve the ImportError in main.py.
    """
    # Inherits: success, reference, status, expires_at, message, ussd_string, amount
    model_config = ConfigDict(from_attributes=True)

    # Specific field for bike tracking if needed
    bike_id: Optional[str] = Field(None, description="Optional internal ID for the assigned bike")


class BikeFreeUsageResponse(BaseModel):
    """
    Response for the remaining free rides endpoint.
    Synchronized with Android's RemainingWithFeeResponse Kotlin class.
    """
    model_config = ConfigDict(from_attributes=True)

    remaining: int = Field(
        ...,
        description="Number of free bike rides the user has left"
    )

    # ✅ 2026 Standard: Informs the UI of the price once free rides are exhausted
    fee: Optional[int] = Field(
        0,
        description="Cost of the bike ride if remaining is 0"
    )