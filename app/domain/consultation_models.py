from pydantic import BaseModel
from typing import Optional
from enum import Enum  #  import Enum


class RequestResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    request_id: Optional[str] = None
    remaining_free_uses: Optional[int] = None
    transaction_id: Optional[str] = None


class UserRoles(str, Enum):  #  make it an Enum
    DOCTOR = "doctor"
    NURSE = "nurse"
    BLOOD_REQUESTER = "blood_request"
    DONOR = "donor"
    TAXI = "taxi"
    BIKE_RIDER = "bike"


class ChannelType(str, Enum):  #  make it an Enum
    CHAT = "chat"
    VOICE = "voice"
    VIDEO = "video"
