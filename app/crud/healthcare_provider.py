from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.healthcare_provider import HealthcareProvider
from app.schemas.healthcare_providers import HealthcareProviderCreate

async def create_provider(db: AsyncSession, prov: HealthcareProviderCreate):
    """
    Creates a new healthcare provider profile.
    Uses model_dump() to handle geo-free structure efficiently.
    """
    obj = HealthcareProvider(**prov.model_dump())
    db.add(obj)
    try:
        await db.commit()
        await db.refresh(obj)
    except IntegrityError:
        # Prevents database hanging on duplicate emails/phones
        await db.rollback()
        raise
    return obj

async def get_providers(db: AsyncSession, skip: int = 0, limit: int = 20,
                        service_type: str = None, name: str = None):
    """
    🔍 THE RESOLVER: Fetches providers with autocomplete-friendly filtering.
    Uses 'ilike' for case-insensitive matching (e.g., 'blue' matches 'Blue Cross').
    """
    stmt = select(HealthcareProvider)

    if service_type:
        stmt = stmt.where(HealthcareProvider.service_type == service_type)

    if name:
        # ✅ Optimized for real-time search: matches any part of the name
        stmt = stmt.where(HealthcareProvider.name.ilike(f"%{name}%"))

    # ✅ Alphabetical ordering is essential for consistent UI dropdowns
    stmt = stmt.order_by(HealthcareProvider.name.asc()).offset(skip).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()

async def get_provider_by_id(db: AsyncSession, provider_id: int):
    """
    Fetch a single provider by ID (used for validation in requests).
    """
    stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    result = await db.execute(stmt)
    return result.scalars().first()

async def update_provider(db: AsyncSession, provider_id: int, update_data: dict):
    """
    Asynchronously updates provider details.
    """
    provider = await get_provider_by_id(db, provider_id)

    if not provider:
        return None

    for key, value in update_data.items():
        if hasattr(provider, key):
            setattr(provider, key, value)

    try:
        await db.commit()
        await db.refresh(provider)
    except IntegrityError:
        await db.rollback()
        raise
    return provider

async def delete_provider(db: AsyncSession, provider_id: int):
    """
    Deletes a provider and ensures the transaction is committed.
    """
    provider = await get_provider_by_id(db, provider_id)

    if not provider:
        return False

    await db.delete(provider)
    await db.commit()
    return True