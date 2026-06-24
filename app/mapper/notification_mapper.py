# =========================================================
# FILE: app/mappers/notification_mapper.py
# =========================================================

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.notification import (
    Notification,
)


class NotificationMapper:
    """
    =========================================================
    NOTIFICATION MAPPER
    =========================================================

    Responsibilities
    ---------------------------------------------------------
    - Serialize notification entities
    - Normalize notification payloads
    - Build safe API response structures
    =========================================================
    """

    # =====================================================
    # SINGLE NOTIFICATION
    # =====================================================
    def to_response(
        self,
        notification: Optional[Notification],
    ) -> Optional[Dict[str, Any]]:

        if not notification:
            return None

        return {
            "id": str(notification.id),
            "user_id": str(
                notification.user_id
            ),
            "title": getattr(
                notification,
                "title",
                None,
            ),
            "body": getattr(
                notification,
                "body",
                None,
            ),
            "type": getattr(
                notification,
                "type",
                None,
            ),
            "data": getattr(
                notification,
                "data",
                {},
            ),
            "is_read": getattr(
                notification,
                "is_read",
                False,
            ),
            "read_at": (
                notification.read_at.isoformat()
                if getattr(
                    notification,
                    "read_at",
                    None,
                )
                else None
            ),
            "created_at": (
                notification.created_at.isoformat()
                if getattr(
                    notification,
                    "created_at",
                    None,
                )
                else None
            ),
        }

    # =====================================================
    # MANY NOTIFICATIONS
    # =====================================================
    def to_response_list(
        self,
        notifications: List[Notification],
    ) -> List[Dict[str, Any]]:

        return [
            self.to_response(item)
            for item in notifications
        ]

    # =====================================================
    # PUSH PAYLOAD
    # =====================================================
    def to_push_payload(
        self,
        *,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        return {
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data or {},
        }


# =========================================================
# SINGLETON
# =========================================================
notification_mapper = NotificationMapper()