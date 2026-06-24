from __future__ import annotations

from typing import Any, Dict, Optional


class UserSerializer:
    """
    =========================================================
    USER SERIALIZER
    =========================================================
    Converts User ORM → API-safe JSON
    =========================================================
    """

    def to_response(self, user: Any) -> Dict[str, Any]:
        return {
            "id": str(user.uid),
            "auth_uid": getattr(user, "auth_uid", None),
            "email": getattr(user, "email", None),
            "name": getattr(user, "name", None),
            "phone": getattr(user, "phone", None),
            "role": getattr(user, "role", None),
            "status": getattr(user, "status", None),
            "is_active": getattr(user, "is_active", True),
            "created_at": (
                user.created_at.isoformat()
                if getattr(user, "created_at", None)
                else None
            ),
            "updated_at": (
                user.updated_at.isoformat()
                if getattr(user, "updated_at", None)
                else None
            ),
        }

    def to_compact(self, user: Any) -> Dict[str, Any]:
        return {
            "id": str(user.uid),
            "name": getattr(user, "name", None),
            "email": getattr(user, "email", None),
        }


user_serializer = UserSerializer()