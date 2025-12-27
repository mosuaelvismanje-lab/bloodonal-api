from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class UserRoles(str, Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    BLOOD_REQUESTER = "blood_request"
    DONOR = "donor"
    TAXI = "taxi"
    BIKE_RIDER = "bike"


class ChannelType(str, Enum):
    CHAT = "chat"
    VOICE = "voice"
    VIDEO = "video"


class RequestResponse(BaseModel):
    success: bool
    message: Optional[str] = None

    # The unique ID of the consultation room or session created
    request_id: Optional[str] = None

    # The provider's payment reference (MTN/Orange)
    transaction_id: Optional[str] = None

    # New: Tracking the cost for the user's receipt
    amount_charged: float = 0.0

    # New: -1 for unlimited, 0 for none, >0 for specific count
    remaining_free_uses: Optional[int] = Field(None, description="-1=unlimited, 0=none")

    # New: To help the frontend handle specific failures (e.g., 'INSUFFICIENT_FUNDS')
    error_code: Optional[str] = None

    class Config:
        from_attributes = True
