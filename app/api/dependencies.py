import firebase_admin
from fastapi import Header, HTTPException, status, Depends
from firebase_admin import auth
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.repositories.user_repository import UserRepository


async def get_current_user_id(Authorization: str = Header(...)) -> str:
    """
    Dependency to get the authenticated user's ID from a Firebase ID token.
    Returns only the UID.
    """
    if not Authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing",
        )

    try:
        # Expecting: "Bearer <token>"
        id_token = Authorization.split(" ")[1]
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token["uid"]
    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"An error occurred: {e}",
        )


async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Dependency to return the full user object from the database,
    using the Firebase UID.
    """
    repo = UserRepository(session)
    user = await repo.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


# If payments.py also needs DB sessions directly
async def get_db_session() -> AsyncSession:
    async for session in get_async_session():
        yield session
