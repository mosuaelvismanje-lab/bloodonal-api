import logging
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Synchronized with the unified 2026 Model
from app.models.service_listing import ServiceUser

logger = logging.getLogger(__name__)

class UserRepository:
    """
    Repository for User profile persistence.
    Standardized for UUID lookups and modular role-based queries.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[ServiceUser]:
        """
        Optimized PK lookup using SQLAlchemy's identity map.
        """
        return await self.session.get(ServiceUser, user_id)

    async def get_user_with_lock(self, user_id: uuid.UUID) -> Optional[ServiceUser]:
        """
        ✅ Pessimistic locking (SELECT FOR UPDATE).
        Prevents race conditions during balance/quota updates.
        """
        stmt = (
            select(ServiceUser)
            .where(ServiceUser.id == user_id)
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_service_user(
        self,
        full_name: str,
        role: str,
        city: str,
        profile_image: Optional[str] = None
    ) -> ServiceUser:
        """
        Registers a new profile in the ecosystem.
        Note: We use flush() so the Orchestrator can commit this along with other actions.
        """
        user = ServiceUser(
            id=uuid.uuid4(),
            full_name=full_name,
            role=role,
            city=city,
            profile_image=profile_image
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(self, user_id: uuid.UUID, **kwargs) -> Optional[ServiceUser]:
        """
        Updates user fields using Postgres RETURNING for atomicity.
        """
        if not kwargs:
            return await self.get_user_by_id(user_id)

        stmt = (
            update(ServiceUser)
            .where(ServiceUser.id == user_id)
            .values(**kwargs)
            .returning(ServiceUser)
        )

        result = await self.session.execute(stmt)
        updated_user = result.scalar_one_or_none()

        if updated_user:
            logger.debug(f"👤 User {user_id} profile updated.")

        return updated_user

    async def find_providers(self, role: str, city: str) -> List[ServiceUser]:
        """
        ✅ MODULAR ADDITION:
        Finds all service providers (donors, drivers) in a specific city.
        Essential for dispatching notifications for new requests.
        """
        stmt = (
            select(ServiceUser)
            .where(
                ServiceUser.role == role,
                ServiceUser.city.ilike(city)
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """
        Removes user and cascades deletions to ServiceListings.
        """
        stmt = delete(ServiceUser).where(ServiceUser.id == user_id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0