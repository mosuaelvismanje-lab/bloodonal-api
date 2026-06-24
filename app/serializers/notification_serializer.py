from __future__ import annotations

from typing import Any, Dict, List, Optional


class NotificationSerializer:
    """
    =========================================================
    NOTIFICATION SERIALIZER
    =========================================================
    """

    def to_response(self, notif: Any) -> Dict[str, Any]:
        return {
            "id": str(notif.id),
            "user_id": str(notif.user_id),
            "title": getattr(notif, "title", None),
            "body": getattr(notif, "body", None),
            "type": getattr(notif, "type", None),
            "category": getattr(notif, "category", None),
            "data": getattr(notif, "data", {}) or {},
            "is_read": getattr(notif, "is_read", False),
            "delivered": getattr(notif, "delivered", False),
            "notification_id": getattr(notif, "notification_id", None),
            "correlation_id": getattr(notif, "correlation_id", None),
            "read_at": (
                notif.read_at.isoformat()
                if getattr(notif, "read_at", None)
                else None
            ),
            "created_at": (
                notif.created_at.isoformat()
                if getattr(notif, "created_at", None)
                else None
            ),
        }

    def to_list(self, items: List[Any]) -> List[Dict[str, Any]]:
        return [self.to_response(i) for i in items]

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


notification_serializer = NotificationSerializer()