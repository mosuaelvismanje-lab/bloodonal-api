from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


# --- Message Schemas ---

class MessageCreate(BaseModel):
    """Schema for creating a new message via REST or WebSocket."""
    room_id: int
    # Supports Firebase UIDs
    sender_id: str = Field(..., example="firebase_uid_123")
    sender_type: str = Field(..., example="patient")  # patient, provider, donor, admin
    content: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    """Schema for outgoing messages with ORM support."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    sender_id: str
    sender_type: str
    content: str
    created_at: datetime
    # ✅ NEW: Helps frontend render names instantly without extra user-profile lookups
    sender_name: Optional[str] = None


# --- Room Schemas ---

class ChatRoomCreate(BaseModel):
    """Schema for creating or finding a chat room linked to a service."""
    request_type: str = Field(..., example="blood_request")
    request_id: int


class ChatRoomOut(BaseModel):
    """Schema for outgoing chat rooms, including message history."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_type: str
    request_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Messages list for the active chat view
    messages: List[MessageOut] = []


class ChatRoomSummary(BaseModel):
    """
    ✅ ENHANCED: Optimized for the 'Inbox' / Conversation List view.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_type: str
    request_id: int
    updated_at: datetime

    # ✅ NEW: For sorting and UI badging
    last_message_content: Optional[str] = Field(None, alias="last_message_preview")
    last_message_at: Optional[datetime] = None
    unread_count: int = 0

    # ✅ NEW: To show "Chat with Dr. Smith" or "Blood Request #102"
    room_display_name: Optional[str] = None