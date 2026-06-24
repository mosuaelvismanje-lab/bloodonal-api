from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class LoginUserDTO(BaseModel):
    """
    =========================================================
    AUTH USER DTO
    =========================================================
    """

    model_config = ConfigDict(
        from_attributes=True,
        frozen=True,
    )

    uid: str
    auth_uid: str

    email: str
    name: str

    role: str

    is_active: bool
    is_verified: bool
    is_admin: bool

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    """
    =========================================================
    AUTH LOGIN RESPONSE
    =========================================================
    """

    model_config = ConfigDict(
        frozen=True,
    )

    success: bool

    message: str

    access_token: Optional[str] = None

    refresh_token: Optional[str] = None

    session_id: Optional[str] = None

    token_type: str = "bearer"

    user: LoginUserDTO

    permissions: list[str] = []

    requires_mfa: bool = False

    requires_verification: bool = False

    login_at: datetime

    expires_at: Optional[datetime] = None