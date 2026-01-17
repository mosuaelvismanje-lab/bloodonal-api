from pydantic import BaseModel, ConfigDict # ✅ Added ConfigDict
from datetime import datetime
from typing import List, Optional

class MessageCreate(BaseModel):
    """Schema for creating a new message."""
    room_id: int
    sender_id: int
    content: str

class MessageOut(BaseModel):
    """Schema for outgoing messages with ORM support."""
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    id: int
    room_id: int
    sender_id: int
    content: str
    created_at: datetime

class ChatRoomCreate(BaseModel):
    """Schema for creating a new chat room."""
    request_type: str
    request_id: int

class ChatRoomOut(BaseModel):
    """Schema for outgoing chat rooms, including nested messages."""
    # ✅ Modern Pydantic V2 Configuration
    model_config = ConfigDict(from_attributes=True)

    id: int
    request_type: str
    request_id: int
    created_at: datetime
    # This will now correctly use MessageOut's config to parse nested objects
    messages: List[MessageOut] = []
