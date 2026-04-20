import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.healthcare_provider import HealthcareProvider
from app.schemas.healthcare_providers import HealthcareProviderCreate

logger = logging.getLogger(__name__)


async def create_provider(db: AsyncSession, prov: HealthcareProviderCreate):
    """
    Creates a new provider. Transaction committed by the caller.
    """
    obj = HealthcareProvider(**prov.model_dump())
    db.add(obj)
    # Commit handled by the router layer
    return obj


async def get_providers(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        service_type: Optional[str] = None,
        name: Optional[str] = None
):
    """
    Fetches providers with fuzzy search and service filtering.
    """
    stmt = select(HealthcareProvider)

    if service_type:
        stmt = stmt.where(HealthcareProvider.service_type == service_type)

    if name:
        stmt = stmt.where(HealthcareProvider.name.ilike(f"%{name}%"))

    stmt = stmt.order_by(HealthcareProvider.name.asc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_provider_by_id(db: AsyncSession, provider_id: int):
    """
    Fetch a single provider by ID for request validation.
    """
    stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_provider(db: AsyncSession, provider_id: int, update_data: dict):
    """
    Updates provider details. Note: exclude 'id' from update_data before calling.
    """
    provider = await get_provider_by_id(db, provider_id)
    if not provider:
        return None

    # Dynamically update provided fields
    for key, value in update_data.items():
        if hasattr(provider, key) and value is not None:
            setattr(provider, key, value)

    # Commit handled by the router layer
    return provider


async def delete_provider(db: AsyncSession, provider_id: int):
    """
    Removes a provider.
    """
    provider = await get_provider_by_id(db, provider_id)
    if not provider:
        return False

    await db.delete(provider)
    # Commit handled by the router layer
    return True