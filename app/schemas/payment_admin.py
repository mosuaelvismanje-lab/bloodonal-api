from pydantic import BaseModel, ConfigDict, Field # ✅ Added ConfigDict
from typing import Optional


class AdminConfirmPaymentRequest(BaseModel):
    """
    Schema for manual payment verification by an administrator.
    Used to bridge the gap between mobile money SMS and the system.
    """
    # ✅ Standard Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    transaction_id: str = Field(..., description="ID from the MTN / Orange SMS")
    payer_phone: str = Field(..., description="Phone number that performed the transfer")
    provider: str = Field(..., description="'MTN' or 'ORANGE'")
    amount: Optional[float] = Field(None, description="Optional safety check for the amount received")
