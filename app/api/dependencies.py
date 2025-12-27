import firebase_admin
from fastapi import Header, HTTPException, status, Depends
from firebase_admin import auth
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import get_async_session
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


async def get_current_user_id(authorization: str = Header(...)) -> str:
    """
    Dependency to get the authenticated user's ID from a Firebase ID token.
    Uses 'authorization' (lowercase) to follow FastAPI/Python conventions.
    """
    # 1. Validate the Scheme
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme. Use 'Bearer <token>'",
        )

    try:
        # 2. Extract and Verify Token
        # split(" ", 1) ensures we only split once for safety
        parts = authorization.split(" ")
        if len(parts) != 2:
            raise ValueError("Token must be Bearer <token>")

        id_token = parts[1]
        decoded_token = auth.verify_id_token(id_token)

        # 3. Return the Firebase UID
        return decoded_token["uid"]

    except firebase_admin.auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
        )
    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )


async def get_current_user(
        user_id: str = Depends(get_current_user_id),
        session: AsyncSession = Depends(get_async_session),
):
    """
    Dependency to return the full user object from the database.
    Ensures the object is compatible with routers expecting .uid or .id.
    """
    repo = UserRepository(session)
    user = await repo.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not registered in the system.",
        )

    # 4. DATA COMPATIBILITY PATCH
    # If your SQLAlchemy model uses 'id' but the payment router uses 'user.uid',
    # we dynamically ensure the attribute exists to prevent AttributeErrors.
    if not hasattr(user, 'uid'):
        user.uid = getattr(user, 'id', user_id)

    return user


async def get_db_session() -> AsyncSession:
    """
    Standard generator for database sessions.
    """
    async for session in get_async_session():
        yield session