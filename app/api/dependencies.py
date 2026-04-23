import logging
import uuid
from typing import Dict, Any, AsyncGenerator, Callable

from fastapi import Header, HTTPException, status, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.config import settings

logger = logging.getLogger(__name__)

# ✅ MOCK SECURITY: allows Swagger testing without JWT
security = HTTPBearer(scheme_name="HTTPBearer", auto_error=False)


# ---------------------------------------------------------
# 1. Hardened Mock User Model (UUID Safe)
# ---------------------------------------------------------
class MockUser:
    def __init__(self, uid: uuid.UUID, email: str, name: str, role: str = "user"):
        self.id = uid
        self.uid = uid
        self.email = email
        self.name = name
        self.role = role
        self.is_active = True
        self.is_admin = (role == "admin" or settings.DEBUG)


# ---------------------------------------------------------
# 2. Admin & Feature Gating
# ---------------------------------------------------------
async def verify_admin_token(x_admin_token: str = Header(None, alias="X-Admin-Token")):
    if not x_admin_token and not settings.DEBUG:
        raise HTTPException(status_code=403, detail="Admin credentials required")

    if not settings.DEBUG and x_admin_token != settings.ADMIN_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

    return x_admin_token or "debug_active"


def require_service_enabled(service_key: str) -> Callable:
    async def _check():
        is_enabled = settings.payment_switches.get(service_key, True)
        if not is_enabled:
            logger.warning(f"🚫 Maintenance mode for: {service_key}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"The {service_key.replace('_', ' ')} service is offline."
            )
        return True

    return _check


# ---------------------------------------------------------
# 3. Auth (Mock / Firebase-ready)
# ---------------------------------------------------------
async def get_current_decoded_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:

    mock_uuid = "550e8400-e29b-41d4-a716-446655440000"

    return {
        "uid": mock_uuid,
        "email": "tester@example.com",
        "name": "Emulator Tester",
        "role": "admin",
    }


async def get_current_user(
    decoded_token: Dict[str, Any] = Depends(get_current_decoded_token),
) -> MockUser:

    return MockUser(
        uid=uuid.UUID(decoded_token["uid"]),
        email=decoded_token.get("email", "unknown@test.com"),
        name=decoded_token.get("name", "Test User"),
        role=decoded_token.get("role", "user"),
    )


async def get_admin_user(
    current_user: MockUser = Depends(get_current_user)
) -> MockUser:

    if not current_user.is_admin:
        logger.warning(f"🚫 Unauthorized admin attempt: {current_user.uid}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required.",
        )

    return current_user


# ---------------------------------------------------------
# 4. Database
# ---------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        try:
            yield session
        except Exception as e:
            logger.error(f"❌ DB Session Error: {e}")
            raise


# ---------------------------------------------------------
# 5. Redis Dependency (FINAL - SINGLE SOURCE)
# ---------------------------------------------------------
async def get_redis(request: Request):
    """
    2026 Redis Standard

    - Redis is created in FastAPI lifespan
    - Stored in app.state.redis
    - This is the ONLY access point

    No fallback, no secondary clients.
    """

    redis = getattr(request.app.state, "redis", None)

    if redis is None:
        logger.error("❌ Redis not initialized in app.state")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service not available",
        )

    return redis


# ---------------------------------------------------------
# 6. Compatibility Aliases
# ---------------------------------------------------------
get_db_session = get_db
get_current_user_id = lambda u=Depends(get_current_user): u.uid