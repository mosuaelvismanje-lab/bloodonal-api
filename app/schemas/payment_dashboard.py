from datetime import datetime
from pydantic import BaseModel, ConfigDict  # ✅ Added ConfigDict
from typing import List, Optional
from app.models.payment import PaymentStatus


class PaymentItem(BaseModel):
    """
    Schema for individual payment records in the admin dashboard.
    Supports direct mapping from SQLAlchemy 'Payment' models.
    """
    # ✅ Modern Pydantic V2 configuration
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    payer_phone: str                # Visible to admin only
    amount: float
    currency: str
    status: PaymentStatus
    provider: str                   # MTN / ORANGE
    provider_tx_id: Optional[str]   # From SMS (manual input)
    created_at: datetime


class PaymentListResponse(BaseModel):
    """
    Schema for paginated payment results.
    """
    # ✅ Added for consistency and V2 compliance
    model_config = ConfigDict(from_attributes=True)

    total: int
    limit: int
    offset: int
    items: List[PaymentItem]
