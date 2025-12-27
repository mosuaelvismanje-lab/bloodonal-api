from pydantic import BaseModel
from typing import Optional


class AdminConfirmPaymentRequest(BaseModel):
    transaction_id: str           # From MTN / Orange SMS
    payer_phone: str              # Phone that sent the money
    provider: str                 # "MTN" or "ORANGE"
    amount: Optional[float] = None  # Optional extra safety check
