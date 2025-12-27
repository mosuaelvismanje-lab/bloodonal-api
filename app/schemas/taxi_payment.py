# app/schemas/taxi_payment.py
from pydantic import BaseModel
from typing import Optional, Dict


class TaxiPaymentRequest(BaseModel):
    user_id: str
    taxi_driver_id: str
    ride_distance_km: Optional[float] = None
    session_metadata: Optional[Dict] = None


class TaxiPaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
