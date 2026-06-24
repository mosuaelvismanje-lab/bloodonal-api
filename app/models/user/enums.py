from __future__ import annotations

from enum import Enum


# =========================================================
# USER GENDER
# =========================================================
class Gender(str, Enum):
    """
    User gender classification.
    """

    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


# =========================================================
# USER LANGUAGE
# =========================================================
class Language(str, Enum):
    """
    Supported platform languages.
    """

    ENGLISH = "en"
    FRENCH = "fr"
    SPANISH = "es"
    PORTUGUESE = "pt"
    ARABIC = "ar"


# =========================================================
# USER THEME PREFERENCE
# =========================================================
class ThemeMode(str, Enum):
    """
    UI appearance preference.
    """

    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


# =========================================================
# AUTH PROVIDERS
# =========================================================
class AuthProvider(str, Enum):
    """
    Authentication providers.
    """

    FIREBASE = "firebase"
    GOOGLE = "google"
    APPLE = "apple"
    FACEBOOK = "facebook"
    PHONE = "phone"
    EMAIL = "email"


# =========================================================
# DEVICE PLATFORM
# =========================================================
class DevicePlatform(str, Enum):
    """
    Supported user platforms.
    """

    ANDROID = "android"
    IOS = "ios"
    WEB = "web"
    DESKTOP = "desktop"


# =========================================================
# USER MEDIA TYPE
# =========================================================
class MediaType(str, Enum):
    """
    Uploaded media classification.
    """

    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"


# =========================================================
# USER LOCATION SOURCE
# =========================================================
class LocationSource(str, Enum):
    """
    Location acquisition method.
    """

    GPS = "gps"
    NETWORK = "network"
    MANUAL = "manual"
    SYSTEM = "system"


# =========================================================
# USER ACTIVITY TYPE
# =========================================================
class UserActivityType(str, Enum):
    """
    Activity tracking categories.
    """

    LOGIN = "login"
    LOGOUT = "logout"
    PROFILE_UPDATE = "profile_update"
    PASSWORD_CHANGE = "password_change"
    LOCATION_UPDATE = "location_update"
    BLOOD_REQUEST_CREATE = "blood_request_create"
    DONATION_ACCEPT = "donation_accept"
    EMERGENCY_TRIGGER = "emergency_trigger"


# =========================================================
# NOTIFICATION TYPE
# =========================================================
class NotificationType(str, Enum):
    """
    User notification categories.
    """

    SYSTEM = "system"
    EMERGENCY = "emergency"
    BLOOD_REQUEST = "blood_request"
    CHAT = "chat"
    PAYMENT = "payment"
    SECURITY = "security"
    PROMOTION = "promotion"


# =========================================================
# USER VISIBILITY
# =========================================================
class ProfileVisibility(str, Enum):
    """
    Public profile visibility level.
    """

    PUBLIC = "public"
    PRIVATE = "private"
    CONTACTS_ONLY = "contacts_only"


# =========================================================
# USER ACCOUNT TYPE
# =========================================================
class AccountType(str, Enum):
    """
    High-level user account classification.
    """

    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    MEDICAL = "medical"
    TRANSPORT = "transport"
    ADMINISTRATIVE = "administrative"


# =========================================================
# EMERGENCY CONTACT RELATIONSHIP
# =========================================================
class EmergencyContactRelationship(str, Enum):
    """
    Emergency contact relationship types.
    """

    PARENT = "parent"
    SIBLING = "sibling"
    SPOUSE = "spouse"
    FRIEND = "friend"
    GUARDIAN = "guardian"
    DOCTOR = "doctor"
    OTHER = "other"


# =========================================================
# WALLET TRANSACTION TYPE
# =========================================================
class WalletTransactionType(str, Enum):
    """
    Wallet transaction operations.
    """

    CREDIT = "credit"
    DEBIT = "debit"
    REFUND = "refund"
    BONUS = "bonus"
    WITHDRAWAL = "withdrawal"


# =========================================================
# SECURITY EVENT TYPE
# =========================================================
class SecurityEventType(str, Enum):
    """
    Security monitoring events.
    """

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_LOCKED = "account_locked"
    DEVICE_ADDED = "device_added"
    DEVICE_REMOVED = "device_removed"


# =========================================================
# USER PRESENCE SOURCE
# =========================================================
class PresenceSource(str, Enum):
    """
    Presence update origin.
    """

    WEBSOCKET = "websocket"
    MOBILE_APP = "mobile_app"
    API = "api"
    SYSTEM = "system"


# =========================================================
# USER DOCUMENT TYPE
# =========================================================
class VerificationDocumentType(str, Enum):
    """
    Identity verification document types.
    """

    NATIONAL_ID = "national_id"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    MEDICAL_LICENSE = "medical_license"
    VOTER_CARD = "voter_card"


# =========================================================
# USER BLOOD TYPE
# =========================================================
