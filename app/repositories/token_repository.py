# app/repositories/token_repository.py

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.models.token import UserToken  # <-- you’ll need to create this model (see below)

logger = logging.getLogger(__name__)


class TokenRepository:
    """
    Repository for handling user FCM tokens.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, user_id: str, token: str) -> None:
        """
        Insert or update an FCM token for a user.
        Ensures one token per user (replace if exists).
        """
        try:
            result = await self.session.execute(
                select(UserToken).where(UserToken.user_id == user_id)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.token = token
                logger.debug("Updated FCM token for user_id=%s", user_id)
            else:
                new_token = UserToken(user_id=user_id, token=token)
                self.session.add(new_token)
                logger.debug("Inserted new FCM token for user_id=%s", user_id)

            await self.session.commit()
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.exception("Failed to upsert FCM token for user_id=%s", user_id)
            raise

    async def get_tokens_by_user(self, user_id: str) -> list[str]:
        """
        Return all tokens for a given user_id.
        """
        try:
            result = await self.session.execute(
                select(UserToken.token).where(UserToken.user_id == user_id)
            )
            tokens = [row[0] for row in result.fetchall()]
            return tokens
        except SQLAlchemyError as e:
            logger.exception("Failed to fetch tokens for user_id=%s", user_id)
            raise
