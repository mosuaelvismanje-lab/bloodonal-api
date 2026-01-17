# app/routers/blood_donor.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session
from app.models.blood_donor import BloodDonor as BloodDonorModel
from app.schemas.blood_donors import (
    BloodDonorCreate,
    BloodDonorUpdate,
    BloodDonor as BloodDonorOut,
)

router = APIRouter(prefix="/blood_donors", tags=["BloodDonors"])


@router.get("/", response_model=List[BloodDonorOut])
async def list_donors(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session)):
    q = await db.execute(select(BloodDonorModel).offset(skip).limit(limit))
    donors = q.scalars().all()
    return donors


@router.get("/{donor_id}", response_model=BloodDonorOut)
async def get_donor(donor_id: int, db: AsyncSession = Depends(get_async_session)):
    q = await db.execute(select(BloodDonorModel).where(BloodDonorModel.id == donor_id))
    donor = q.scalars().first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")
    return donor


@router.post("/", response_model=BloodDonorOut, status_code=status.HTTP_201_CREATED)
async def create_donor(donor_in: BloodDonorCreate, db: AsyncSession = Depends(get_async_session)):
    data = donor_in.model_dump() if hasattr(donor_in, "model_dump") else donor_in.model_dump()
    new = BloodDonorModel(**data)
    db.add(new)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        detail = "Phone number already exists" if "unique" in str(e.orig).lower() else "Could not create donor"
        raise HTTPException(status_code=400, detail=detail)
    await db.refresh(new)
    return new


@router.put("/{donor_id}", response_model=BloodDonorOut)
async def update_donor(donor_id: int, donor_in: BloodDonorUpdate, db: AsyncSession = Depends(get_async_session)):
    q = await db.execute(select(BloodDonorModel).where(BloodDonorModel.id == donor_id))
    donor = q.scalars().first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")

    data = donor_in.model_dump(exclude_unset=True) if hasattr(donor_in, "model_dump") else donor_in.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(donor, field, value)
    db.add(donor)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        detail = "Phone number already exists" if "unique" in str(e.orig).lower() else "Could not update donor"
        raise HTTPException(status_code=400, detail=detail)
    await db.refresh(donor)
    return donor


@router.delete("/{donor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_donor(donor_id: int, db: AsyncSession = Depends(get_async_session)):
    q = await db.execute(select(BloodDonorModel).where(BloodDonorModel.id == donor_id))
    donor = q.scalars().first()
    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")
    await db.delete(donor)
    await db.commit()
    return None

