from __future__ import annotations

from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


# =========================================================
# 🔔 NOTIFICATION CREATE SCHEMA (ENTERPRISE)
# =========================================================
class NotificationCreate(BaseModel):
    """
    =========================================================
    🔔 ENTERPRISE NOTIFICATION PAYLOAD CONTRACT
    =========================================================

    This is the SINGLE SOURCE OF TRUTH between:
    ✔ FastAPI backend
    ✔ NotificationGatewayImpl
    ✔ Firebase Cloud Messaging
    ✔ Flutter NotificationItem model
    ✔ Analytics & audit logging
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # =========================================================
    # EVENT METADATA
    # =========================================================
    event: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Event identifier e.g. blood.request.created",
    )

    status: str = Field(
        default="received",
        min_length=2,
        max_length=30,
    )

    # =========================================================
    # CONTENT
    # =========================================================
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    message: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    body: str = Field(
        default="",
        max_length=1000,
    )

    sub_type: str = Field(
        default="generic",
        max_length=50,
    )

    # =========================================================
    # SERVICE DOMAIN (CRITICAL FOR YOUR SYSTEM)
    # =========================================================
    service_type: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="Used in Flutter as item.serviceType",
    )

    category: str = Field(
        ...,
        min_length=2,
        max_length=50,
    )

    listing_id: str = Field(
        default="",
        max_length=100,
    )

    # =========================================================
    # ACTORS
    # =========================================================
    user_id: str = Field(
        ...,
        description="Recipient user ID",
    )

    sender_id: Optional[str] = Field(
        default=None,
        description="Optional sender (donor/provider/system)",
    )

    # =========================================================
    # CONTACT / LOCATION
    # =========================================================
    location: Optional[str] = Field(
        default="",
        max_length=255,
    )

    phone: Optional[str] = Field(
        default="",
        max_length=30,
    )

    # =========================================================
    # EXTRA PAYLOAD (FLEXIBILITY LAYER)
    # =========================================================
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional raw payload from services or FCM",
    )

    # =========================================================
    # OPTIONAL CLIENT CONTROL FLAGS
    # =========================================================
    silent: Optional[bool] = Field(
        default=False,
        description="If true, do not show UI notification",
    )

    priority: Optional[str] = Field(
        default="normal",
        pattern="^(low|normal|high|urgent)$",
    )