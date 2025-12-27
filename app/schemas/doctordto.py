from pydantic import BaseModel
from typing import Optional
from enum import Enum

# -----------------------------
# Doctor DTO
# -----------------------------
class DoctorDto(BaseModel):
    id: str
    name: str
    is_online: bool

    model_config = {"from_attributes": True}  # Pydantic V2 replacement for orm_mode

# -----------------------------
# Request / Response
# -----------------------------
class RequestResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    request_id: Optional[str] = None
    remaining_free_uses: Optional[int] = None
    transaction_id: Optional[str] = None

# -----------------------------
# Optional: Use Enums for roles/channels
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
