# app/schemas/chat.py

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class MessageCreate(BaseModel):
    room_id: int
    sender_id: int
    content: str

class MessageOut(BaseModel):
    id: int
    room_id: int
    sender_id: int
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class ChatRoomCreate(BaseModel):
    request_type: str
    request_id: int

class ChatRoomOut(BaseModel):
    id: int
    request_type: str
    request_id: int
    created_at: datetime
    messages: Optional[List[MessageOut]] = []

    class Config:
        from_attributes = True
