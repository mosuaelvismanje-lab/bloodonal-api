from __future__ import annotations

from typing import Any, Dict, List


class AuditSerializer:
    """
    =========================================================
    AUDIT SERIALIZER
    =========================================================
    Used for:
    - notifications audit logs
    - security logs
    - system tracking
    =========================================================
    """

    def to_response(self, audit: Any) -> Dict[str, Any]:
        return {
            "id": str(getattr(audit, "id", "")),
            "event": getattr(audit, "event", None),
            "entity_type": getattr(audit, "entity_type", None),
            "entity_id": getattr(audit, "entity_id", None),
            "user_id": getattr(audit, "user_id", None),
            "status": getattr(audit, "status", None),
            "metadata": getattr(audit, "metadata", {}) or {},
            "ip_address": getattr(audit, "ip_address", None),
            "created_at": (
                audit.created_at.isoformat()
                if getattr(audit, "created_at", None)
                else None
            ),
        }

    def to_list(self, items: List[Any]) -> List[Dict[str, Any]]:
        return [self.to_response(i) for i in items]


audit_serializer = AuditSerializer()