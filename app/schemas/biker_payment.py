# app/schemas/biker_payment.py
from pydantic import BaseModel
from typing import Optional, Dict


class BikerPaymentRequest(BaseModel):
    user_id: str
    biker_id: str
    ride_distance_km: Optional[float] = None
    session_metadata: Optional[Dict] = None


class BikerPaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str]
    status: Optional[str] = None
    message: Optional[str] = None
