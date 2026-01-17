from pydantic import BaseModel, ConfigDict, Field # ✅ Added ConfigDict
from typing import Optional
from enum import Enum

# -----------------------------
# Doctor DTO
# -----------------------------
class DoctorDto(BaseModel):
    # ✅ Use ConfigDict instead of a raw dictionary
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    is_online: bool

# -----------------------------
# Request / Response
# -----------------------------
class RequestResponse(BaseModel):
    # ✅ Added for consistency and to allow direct ORM mapping
    model_config = ConfigDict(from_attributes=True)

    success: bool
    message: Optional[str] = None
    request_id: Optional[str] = None
    remaining_free_uses: Optional[int] = None
    transaction_id: Optional[str] = None

# -----------------------------
# Enums (No changes needed here)
# -----------------------------
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
