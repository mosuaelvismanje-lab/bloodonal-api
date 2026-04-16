from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.blood_donor import BloodDonor
from app.schemas.blood_donors import BloodDonorCreate, BloodDonorUpdate


async def create_donor(db: AsyncSession, donor: BloodDonorCreate) -> BloodDonor:
    """
    Create a new BloodDonor record asynchronously.
    Payload automatically excludes lat/lon based on the updated Pydantic schema.
    """
    # ✅ Using model_dump() is perfect here—it ensures we only pass fields
    # that actually exist in the schema to the database model.
    obj = BloodDonor(**donor.model_dump())
    db.add(obj)
    try:
        await db.commit()
        await db.refresh(obj)
    except IntegrityError:
        await db.rollback()
        raise
    return obj


async def get_donors(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[BloodDonor]:
    """
    Return a list of donors using the Async Select pattern.
    """
    result = await db.execute(
        select(BloodDonor).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def get_donor(db: AsyncSession, donor_id: int) -> Optional[BloodDonor]:
    """
    Fetch a single donor by ID using Async Select.
    """
    result = await db.execute(
        select(BloodDonor).where(BloodDonor.id == donor_id)
    )
    return result.scalars().first()


async def update_donor(db: AsyncSession, donor_id: int, donor_update: BloodDonorUpdate) -> Optional[BloodDonor]:
    """
    Update an existing donor. Only fields explicitly set in the request are changed.
    """
    donor = await get_donor(db, donor_id)
    if not donor:
        return None

    # ✅ exclude_unset=True ensures we don't overwrite existing data with 'None'
    data = donor_update.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(donor, field, value)

    db.add(donor)
    try:
        await db.commit()
        await db.refresh(donor)
    except IntegrityError:
        await db.rollback()
        raise
    return donor


async def delete_donor(db: AsyncSession, donor_id: int) -> bool:
    """
    Delete a donor by ID. Returns True if deleted, False if not found.
    """
    donor = await get_donor(db, donor_id)
    if not donor:
        return False

    await db.delete(donor)
    await db.commit()
    return True