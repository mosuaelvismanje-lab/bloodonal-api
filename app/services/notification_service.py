# File: app/services/notification_service.py
from typing import Optional

from app.firebase_client import send_fcm_to_donor


class NotificationService:
    """
    Wraps your firebase_app helper for push notifications.
    Could also route through Cloud Functions if you prefer.
    """
    async def send_push(
        self,
        fcm_token: str,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
    ) -> Optional[str]:
        # You could offload this to a background task / threadpool if it's slow.
        return send_fcm_to_donor(fcm_token, title, body, data)
