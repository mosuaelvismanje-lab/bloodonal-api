# File: app/schemas/notification.py
from pydantic import BaseModel, ConfigDict  # ✅ Added ConfigDict
from typing import Optional
from datetime import datetime


class FcmTokenUpdate(BaseModel):
    # ✅ Standardizes the model for Pydantic V2
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    token: str


class NotificationDto(BaseModel):
    """
    Data Transfer Object for Notifications.
    Supports mapping directly from SQLAlchemy objects via from_attributes.
    """
    # ✅ Replaces old-style ORM configuration
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: Optional[str] = None
    sub_type: str
    message: str
    location: str
    phone: str
    timestamp: int
    read: bool = False
    created_at: Optional[datetime] = None


class PushNotification(BaseModel):
    # ✅ Standardizes the model for Pydantic V2
    model_config = ConfigDict(from_attributes=True)

    title: str
    body: str
    topic: Optional[str] = None
    data: Optional[dict] = None
