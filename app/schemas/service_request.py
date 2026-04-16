# app/schemas/service_request.py
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class UniversalServiceRequest(BaseModel):
    service_type: str = Field(..., pattern="^(blood|taxi|doctor|nurse)$")
    city: str
    phone: str
    # ✅ Service-specific data goes here
    # Example: {"blood_group": "O+", "hospital": "General Hospital"}
    details: Dict[str, Any] = {}

    amount: float = 0.0
    idempotency_key: Optional[str] = None