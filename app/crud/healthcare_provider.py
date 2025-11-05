# app/crud/healthcare_provider.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from app.models.healthcare_provider import HealthcareProvider
from app.schemas.healthcare_providers import HealthcareProviderCreate


async def create_provider(db: AsyncSession, prov: HealthcareProviderCreate):
    obj = HealthcareProvider(**prov.dict())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return obj


async def get_providers(db: AsyncSession, skip: int = 0, limit: int = 100,
                        service_type: str = None, name: str = None):
    stmt = select(HealthcareProvider)

    if service_type:
        stmt = stmt.where(HealthcareProvider.service_type == service_type)

    if name:
        stmt = stmt.where(HealthcareProvider.name.ilike(f"%{name}%"))

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_provider_by_id(db: AsyncSession, provider_id: int):
    stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    result = await db.execute(stmt)
    return result.scalars().first()


async def update_provider(db: AsyncSession, provider_id: int, update_data: dict):
    stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalars().first()

    if not provider:
        return None

    for key, value in update_data.items():
        setattr(provider, key, value)

    await db.commit()
    await db.refresh(provider)
    return provider


async def delete_provider(db: AsyncSession, provider_id: int):
    stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    result = await db.execute(stmt)
    provider = result.scalars().first()

    if not provider:
        return False

    await db.delete(provider)
    await db.commit()
    return True
