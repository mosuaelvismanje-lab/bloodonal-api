import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Production Standard: Use unified dependencies and security
from app.api.dependencies import get_db_session, get_current_user
from app.models.blood_donor import BloodDonor as BloodDonorModel
from app.schemas.blood_donors import (
    BloodDonorCreate,
    BloodDonorUpdate,
    BloodDonor as BloodDonorOut,
)

logger = logging.getLogger(__name__)

# Versioning: Prefix set to /v1/blood-donors
router = APIRouter(prefix="/blood-donors", tags=["BloodDonors"])


# -------------------------------------------------
# LIST & FILTER DONORS
# -------------------------------------------------
@router.get("/", response_model=List[BloodDonorOut])
async def list_donors(
        skip: int = 0,
        limit: int = 100,
        blood_type: Optional[str] = Query(None, description="Filter by type, e.g., 'O+' or 'UNKNOWN'"),
        city: Optional[str] = Query(None, description="Filter by city"),
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    """
    Returns a list of blood donors. Supports filtering by blood type and city.
    """
    query = select(BloodDonorModel).offset(skip).limit(limit).order_by(BloodDonorModel.id)

    # Dynamic Filtering
    if blood_type:
        query = query.where(BloodDonorModel.blood_type == blood_type.upper())
    if city:
        query = query.where(BloodDonorModel.city.ilike(f"%{city}%"))

    result = await db.execute(query)
    donors = result.scalars().all()
    return donors


# -------------------------------------------------
# GET SINGLE DONOR
# -------------------------------------------------
@router.get("/{donor_id}", response_model=BloodDonorOut)
async def get_donor(
        donor_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    query = select(BloodDonorModel).where(BloodDonorModel.id == donor_id)
    result = await db.execute(query)
    donor = result.scalars().first()

    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")
    return donor


# -------------------------------------------------
# CREATE DONOR
# -------------------------------------------------
@router.post("/", response_model=BloodDonorOut, status_code=status.HTTP_201_CREATED)
async def create_donor(
        donor_in: BloodDonorCreate,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    """
    Registers a new blood donor.
    If blood_type is missing, schema defaults it to 'UNKNOWN'.
    """
    new_donor = BloodDonorModel(**donor_in.model_dump())
    db.add(new_donor)

    try:
        await db.commit()
        await db.refresh(new_donor)
        return new_donor
    except IntegrityError as e:
        await db.rollback()
        # Handle unique constraint on phone
        if "unique" in str(e.orig).lower() or "already exists" in str(e.orig).lower():
            raise HTTPException(
                status_code=400,
                detail="Phone number already registered"
            )
        logger.error(f"DB Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# -------------------------------------------------
# UPDATE DONOR
# -------------------------------------------------
@router.put("/{donor_id}", response_model=BloodDonorOut)
async def update_donor(
        donor_id: int,
        donor_in: BloodDonorUpdate,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    query = select(BloodDonorModel).where(BloodDonorModel.id == donor_id)
    result = await db.execute(query)
    donor = result.scalars().first()

    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")

    # Partial update logic
    update_data = donor_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "blood_type" and value:
            setattr(donor, field, value.upper())
        else:
            setattr(donor, field, value)

    try:
        await db.commit()
        await db.refresh(donor)
        return donor
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Update failed: Phone number conflict"
        )


# -------------------------------------------------
# DELETE DONOR
# -------------------------------------------------
@router.delete("/{donor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_donor(
        donor_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    query = select(BloodDonorModel).where(BloodDonorModel.id == donor_id)
    result = await db.execute(query)
    donor = result.scalars().first()

    if not donor:
        raise HTTPException(status_code=404, detail="Donor not found")

    try:
        await db.delete(donor)
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Deletion failed for donor {donor_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    return None