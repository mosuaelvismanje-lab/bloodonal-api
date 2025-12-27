# File: app/schemas/notification.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class FcmTokenUpdate(BaseModel):
    user_id: str
    token: str


class NotificationDto(BaseModel):
    id: str
    user_id: str
    title: Optional[str] = None            # optional title
    sub_type: str                           # e.g., "incoming_call", "alert"
    message: str                            # main message body
    location: str
    phone: str
    timestamp: int                          # epoch millis
    read: bool = False
    created_at: Optional[datetime] = None   # creation timestamp


class PushNotification(BaseModel):
    title: str
    body: str
    topic: Optional[str] = None  # repurposed as single-device FCM token
    data: Optional[dict] = None  # optional custom payload (key-value pairs)
