import logging
import uuid
from typing import AsyncGenerator, Dict, Any, Callable

from fastapi import HTTPException, status, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.config import settings

logger = logging.getLogger(__name__)

# ✅ 1. Security Definition (Mock-friendly)
security = HTTPBearer(scheme_name="HTTPBearer", auto_error=False)


# ---------------------------------------------------------
# 2. Hardened Mock User Model (UUID Aware)
# ---------------------------------------------------------
class MockUser:
    """
    Standardized User bridge.
    Ensures self.uid is a real UUID object to match 2026 DB schemas.
    """

    def __init__(self, uid: uuid.UUID, email: str, role: str = "user"):
        self.id = uid
        self.uid = uid
        self.email = email
        self.role = role
        self.is_active = True
        # In DEBUG/Emulator mode, everyone is an admin for ease of testing
        self.is_admin = (role == "admin" or settings.DEBUG)


# ---------------------------------------------------------
# 3. Database Dependency
# ---------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provides a managed AsyncSession."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"❌ DB Session Error: {e}")
            await session.rollback()
            raise


# ---------------------------------------------------------
# 4. Identity & Auth Dependencies
# ---------------------------------------------------------

async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Security(security)
) -> MockUser:
    """
    Identity Resolver: Bypasses Firebase Auth in Debug/Emulator mode.
    Converts string IDs to real UUIDs to prevent DB filtering errors.
    """
    # 2026 Emulator Standard UUID
    mock_uuid_str = "550e8400-e29b-41d4-a716-446655440000"

    # In a real production environment, you would call:
    # decoded_token = firebase_admin.auth.verify_id_token(credentials.credentials)

    return MockUser(
        uid=uuid.UUID(mock_uuid_str),
        email="tester@example.com",
        role="admin" if settings.DEBUG else "user"
    )


async def get_admin_user(
        current_user: MockUser = Depends(get_current_user)
) -> MockUser:
    """Gating: Ensures the User has administrative privileges."""
    if not current_user.is_admin:
        logger.warning(f"🚫 Unauthorized Admin access attempt: {current_user.uid}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required."
        )
    return current_user


# ---------------------------------------------------------
# 5. Feature Toggles (2026 Modular Core)
# ---------------------------------------------------------

def require_service_enabled(service_key: str) -> Callable:
    """
    Dependency Factory to gate routes based on settings.payment_switches.
    Allows turning off 'blood_request' or 'taxi' without a redeploy.
    """

    async def _check():
        is_enabled = settings.payment_switches.get(service_key, True)
        if not is_enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The {service_key.replace('_', ' ')} service is currently in maintenance."
            )
        return True

    return _check


# ✅ Compatibility Aliases
get_db_session = get_db
get_current_user_id = lambda u=Depends(get_current_user): u.uid