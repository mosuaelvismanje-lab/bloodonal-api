# =========================================================
# FILE: app/models/user/statuses.py
# =========================================================

from __future__ import annotations

from enum import Enum


# =========================================================
# USER ACCOUNT STATUS
# =========================================================
class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"
    PENDING = "pending"
    DELETED = "deleted"


# =========================================================
# USER ONLINE STATUS
# =========================================================
class UserPresenceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    BUSY = "busy"
    INVISIBLE = "invisible"


# =========================================================
# USER VERIFICATION STATUS
# =========================================================
class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


# =========================================================
# DEVICE STATUS
# =========================================================
class DeviceStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    BLOCKED = "blocked"


# =========================================================
# SESSION STATUS
# =========================================================
class SessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    LOGGED_OUT = "logged_out"


# =========================================================
# NOTIFICATION STATUS
# =========================================================
class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


# =========================================================
# EMERGENCY CONTACT STATUS
# =========================================================
class EmergencyContactStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNVERIFIED = "unverified"


# =========================================================
# USER MEDIA STATUS
# =========================================================
class MediaStatus(str, Enum):
    ACTIVE = "active"
    PROCESSING = "processing"
    FLAGGED = "flagged"
    DELETED = "deleted"


# =========================================================
# BLOCK STATUS
# =========================================================
class BlockStatus(str, Enum):
    ACTIVE = "active"
    REMOVED = "removed"


# =========================================================
# WALLET STATUS
# =========================================================
class WalletStatus(str, Enum):
    ACTIVE = "active"
    FROZEN = "frozen"
    CLOSED = "closed"


# =========================================================
# AUDIT EVENT STATUS
# =========================================================
class AuditEventStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    WARNING = "warning"


# =========================================================
# USER RATING STATUS
# =========================================================
class RatingStatus(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    REMOVED = "removed"