from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from app.models.payment import PaymentStatus


class PaymentItem(BaseModel):
    id: str
    user_id: str

    payer_phone: str                # Visible to admin only
    amount: float
    currency: str

    status: PaymentStatus

    provider: str                   # MTN / ORANGE

    provider_tx_id: Optional[str]   # From SMS (manual input)

    created_at: datetime

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[PaymentItem]
