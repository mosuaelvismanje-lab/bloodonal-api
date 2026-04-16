import logging
import uuid
from typing import List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert

from app.models.token import UserToken

logger = logging.getLogger(__name__)

class TokenRepository:
    """
    Repository for handling user FCM (Firebase Cloud Messaging) tokens.
    Supports multi-device logic (one user, many tokens).
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_token(self, user_id: uuid.UUID, token: str) -> None:
        """
        Insert or update an FCM token.
        Ensures a token is always linked to the most recent user session.
        """
        try:
            # PostgreSQL UPSERT logic
            stmt = insert(UserToken).values(
                user_id=user_id,
                token=token
            )

            # If this token exists elsewhere, re-assign it to this user
            stmt = stmt.on_conflict_do_update(
                index_elements=['token'],
                set_={'user_id': user_id}
            )

            await self.session.execute(stmt)
            # Use flush for transactional integrity, or commit for standalone updates
            await self.session.flush()
            logger.debug(f"FCM Token upserted for user {user_id}")
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Failed to upsert token: {e}")
            raise

    async def get_tokens_by_user(self, user_id: uuid.UUID) -> List[str]:
        """
        Fetches all registered tokens for a specific user.
        Used when a user needs a direct notification (e.g., 'Payment Success').
        """
        try:
            stmt = select(UserToken.token).where(UserToken.user_id == user_id)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Error fetching tokens for {user_id}: {e}")
            return []

    async def get_tokens_for_users(self, user_ids: List[uuid.UUID]) -> List[str]:
        """
        ✅ MODULAR ADDITION:
        Fetches tokens for a batch of users.
        Critical for broadcasting (e.g., alerting all donors in a city).
        """
        try:
            stmt = select(UserToken.token).where(UserToken.user_id.in_(user_ids))
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            logger.error(f"Batch token fetch failed: {e}")
            return []

    async def remove_token(self, token: str) -> None:
        """
        Removes invalid tokens.
        Essential for handling 'NotRegistered' errors from Firebase.
        """
        try:
            stmt = delete(UserToken).where(UserToken.token == token)
            await self.session.execute(stmt)
            await self.session.flush()
            logger.info("Invalid token removed.")
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"Failed to remove token: {e}")
            raise