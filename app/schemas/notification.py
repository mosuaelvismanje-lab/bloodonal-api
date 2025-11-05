# app/schemas/notification.py
from pydantic import BaseModel
from typing import Optional


class FcmTokenUpdate(BaseModel):
    user_id: str
    token: str


class NotificationDto(BaseModel):
    id: str
    user_id: str
    title: str
    body: str
    read: bool = False


class PushNotification(BaseModel):
    title: str
    body: str
    topic: Optional[str] = None  # repurposed as single-device FCM token
