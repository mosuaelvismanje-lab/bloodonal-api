from pydantic import BaseModel, ConfigDict # ✅ Added ConfigDict
from typing import Optional, Dict


class TaxiPaymentRequest(BaseModel):
    """
    Schema for initiating a taxi ride payment.
    """
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    taxi_driver_id: str
    ride_distance_km: Optional[float] = None
    session_metadata: Optional[Dict] = None


class TaxiPaymentResponse(BaseModel):
    """
    Standardized response for taxi payment status.
    """
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
