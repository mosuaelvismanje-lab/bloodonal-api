from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID  # ✅ Required to handle Postgres UUID objects


class FcmTokenUpdate(BaseModel):
    """
    Schema for updating/registering a device token.
    """
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    token: str


class NotificationDto(BaseModel):
    """
    Data Transfer Object for Notifications.
    Fixed: id is now UUID to match database output and prevent validation errors.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID  # ✅ Use UUID to handle the native database type
    user_id: str
    title: Optional[str] = "No Title"
    sub_type: str = "generic"
    message: str
    location: Optional[str] = "N/A"
    phone: Optional[str] = "N/A"
    timestamp: Optional[int] = None
    read: bool = False
    created_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None # Added to show custom payload in history


class PushNotification(BaseModel):
    """
    Schema for sending a push notification request.
    """
    model_config = ConfigDict(from_attributes=True)

    title: str
    body: str
    user_id: Optional[str] = "unknown"
    topic: Optional[str] = None
    data: Optional[Dict[str, Any]] = None