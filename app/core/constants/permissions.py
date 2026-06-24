# =========================================================
# FILE: app/models/user/permissions.py
# =========================================================

from __future__ import annotations

from enum import Enum


class Permission(str, Enum):
    """
    =========================================================
    PLATFORM PERMISSIONS (RBAC SYSTEM)
    =========================================================

    Enterprise-grade permission registry.

    Rules:
    - Roles are collections of permissions
    - Never hardcode permissions in business logic
    - Always check permissions via middleware/services
    """

    # =====================================================
    # USER MANAGEMENT
    # =====================================================

    USER_CREATE = "user:create"
    USER_READ = "user:read"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_BAN = "user:ban"
    USER_VERIFY = "user:verify"

    # =====================================================
    # PROFILE
    # =====================================================

    PROFILE_READ = "profile:read"
    PROFILE_UPDATE = "profile:update"
    PROFILE_UPLOAD_MEDIA = "profile:upload_media"

    # =====================================================
    # LOCATION + PRESENCE
    # =====================================================

    LOCATION_UPDATE = "location:update"
    LOCATION_READ = "location:read"
    PRESENCE_UPDATE = "presence:update"

    # =====================================================
    # BLOOD SYSTEM
    # =====================================================

    BLOOD_REQUEST_CREATE = "blood_request:create"
    BLOOD_REQUEST_READ = "blood_request:read"
    BLOOD_REQUEST_UPDATE = "blood_request:update"
    BLOOD_REQUEST_DELETE = "blood_request:delete"

    DONATION_CREATE = "donation:create"
    DONATION_READ = "donation:read"

    BLOOD_INVENTORY_READ = "blood_inventory:read"
    BLOOD_INVENTORY_UPDATE = "blood_inventory:update"

    # =====================================================
    # HOSPITAL
    # =====================================================

    HOSPITAL_CREATE = "hospital:create"
    HOSPITAL_READ = "hospital:read"
    HOSPITAL_UPDATE = "hospital:update"
    HOSPITAL_DELETE = "hospital:delete"

    # =====================================================
    # AMBULANCE / TRANSPORT
    # =====================================================

    TRANSPORT_CREATE = "transport:create"
    TRANSPORT_READ = "transport:read"
    TRANSPORT_UPDATE = "transport:update"
    TRANSPORT_DELETE = "transport:delete"

    LIVE_TRACKING_ACCESS = "tracking:access"

    # =====================================================
    # EMERGENCY SYSTEM
    # =====================================================

    EMERGENCY_CREATE = "emergency:create"
    EMERGENCY_READ = "emergency:read"
    EMERGENCY_RESPOND = "emergency:respond"
    EMERGENCY_CLOSE = "emergency:close"

    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    NOTIFICATION_SEND = "notification:send"
    NOTIFICATION_READ = "notification:read"
    NOTIFICATION_DELETE = "notification:delete"

    PUSH_TOKEN_REGISTER = "push_token:register"

    # =====================================================
    # WALLET / PAYMENTS
    # =====================================================

    WALLET_READ = "wallet:read"
    WALLET_UPDATE = "wallet:update"

    TRANSACTION_CREATE = "transaction:create"
    TRANSACTION_READ = "transaction:read"

    PAYOUT_CREATE = "payout:create"
    PAYOUT_APPROVE = "payout:approve"

    # =====================================================
    # ANALYTICS
    # =====================================================

    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"

    # =====================================================
    # ADMIN
    # =====================================================

    ADMIN_PANEL_ACCESS = "admin:panel_access"

    ROLE_ASSIGN = "role:assign"
    PERMISSION_ASSIGN = "permission:assign"

    SYSTEM_SETTINGS_UPDATE = "system_settings:update"

    AUDIT_READ = "audit:read"

    # =====================================================
    # SUPER ADMIN
    # =====================================================

    SUPER_ADMIN_ACCESS = "super_admin:access"
   