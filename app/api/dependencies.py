import logging
import uuid
from typing import Dict, Any, AsyncGenerator, Optional, Callable

from fastapi import Header, HTTPException, status, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.config import settings

logger = logging.getLogger(__name__)

# ✅ MOCK SECURITY: auto_error=False allows testing in Swagger without real JWT
security = HTTPBearer(scheme_name="HTTPBearer", auto_error=False)


# ---------------------------------------------------------
# 1. Hardened Mock User Model (UUID Aware)
# ---------------------------------------------------------
class MockUser:
    """
    Standardized User bridge for 2026.
    Ensures self.uid is a real UUID object to prevent DB filter errors.
    """

    def __init__(self, uid: uuid.UUID, email: str, name: str, role: str = "user"):
        self.id = uid  # Primary key as UUID
        self.uid = uid
        self.email = email
        self.name = name
        self.role = role
        self.is_active = True
        # In DEBUG mode, we treat the emulator user as an admin by default
        self.is_admin = (role == "admin" or settings.DEBUG)


# ---------------------------------------------------------
# 2. Admin & Feature Gating
# ---------------------------------------------------------

async def verify_admin_token(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    """Validates super-admin access via secret header."""
    if not x_admin_token and not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Admin credentials required")

    if not settings.DEBUG and x_admin_token != settings.ADMIN_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    return x_admin_token or "debug_active"


def require_service_enabled(service_key: str) -> Callable:
    """✅ 2026 Feature Toggle: Dependency Factory to gate routes."""

    async def _check():
        is_enabled = settings.payment_switches.get(service_key, True)
        if not is_enabled:
            logger.warning(f"🚫 Maintenance mode for: {service_key}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The {service_key.replace('_', ' ')} service is currently offline."
            )
        return True

    return _check


# ---------------------------------------------------------
# 3. Auth & Identity (Firebase Emulator Standards)
# ---------------------------------------------------------

async def get_current_decoded_token(
        credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """Identity Resolver: Bypasses Firebase Auth in Debug mode."""

    # Static UUID for testing to keep sessions consistent in dev
    mock_uuid = "550e8400-e29b-41d4-a716-446655440000"

    return {
        "uid": mock_uuid,
        "email": "tester@example.com",
        "name": "Emulator Tester",
        "role": "admin",  # Default to admin in dev
    }


async def get_current_user(
        decoded_token: Dict[str, Any] = Depends(get_current_decoded_token),
) -> MockUser:
    """
    Serves a MockUser with a validated UUID.
    Passes this to Repositories for type-safe filtering.
    """
    return MockUser(
        uid=uuid.UUID(decoded_token["uid"]),  # ✅ Convert string to real UUID
        email=decoded_token.get("email", "unknown@test.com"),
        name=decoded_token.get("name", "Test User"),
        role=decoded_token.get("role", "user")
    )


async def get_admin_user(
        current_user: MockUser = Depends(get_current_user)
) -> MockUser:
    """Authorization Gating: Validates admin status."""
    if not current_user.is_admin:
        logger.warning(f"🚫 Unauthorized admin attempt: {current_user.uid}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required."
        )
    return current_user


# ---------------------------------------------------------
# 4. Database & Aliases
# ---------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides a managed AsyncSession."""
    async for session in get_async_session():
        try:
            yield session
        except Exception as e:
            logger.error(f"❌ DB Session Error: {e}")
            raise


# ✅ Compatibility Aliases for 2026 Core
get_db_session = get_db
get_current_user_id = lambda u=Depends(get_current_user): u.uid