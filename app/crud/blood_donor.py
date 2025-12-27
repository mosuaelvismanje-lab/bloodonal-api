# app/crud/blood_donor.py

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.blood_donor import BloodDonor
from app.schemas.blood_donors import BloodDonorCreate, BloodDonorUpdate

def create_donor(db: Session, donor: BloodDonorCreate) -> BloodDonor:
    """
    Create a new BloodDonor record.
    Raises IntegrityError if, e.g., phone uniqueness is violated.
    """
    payload = donor.model_dump() if hasattr(donor, "model_dump") else donor.dict()
    obj = BloodDonor(**payload)
    db.add(obj)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(obj)
    return obj

def get_donors(db: Session, skip: int = 0, limit: int = 100) -> List[BloodDonor]:
    """
    Return a list of donors with offset and limit.
    """
    return db.query(BloodDonor).offset(skip).limit(limit).all()

def get_donor(db: Session, donor_id: int) -> Optional[BloodDonor]:
    """
    Fetch a single donor by ID. Returns None if not found.
    """
    return db.query(BloodDonor).filter(BloodDonor.id == donor_id).first()

def update_donor(db: Session, donor_id: int, donor_update: BloodDonorUpdate) -> Optional[BloodDonor]:
    """
    Update fields of an existing donor. Only fields set in donor_update are changed.
    Returns the updated instance, or None if not found.
    Raises IntegrityError on duplicate phone, etc.
    """
    donor = get_donor(db, donor_id)
    if not donor:
        return None

    data = (
        donor_update.model_dump(exclude_unset=True)
        if hasattr(donor_update, "model_dump")
        else donor_update.dict(exclude_unset=True)
    )
    for field, value in data.items():
        setattr(donor, field, value)
    db.add(donor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    db.refresh(donor)
    return donor

def delete_donor(db: Session, donor_id: int) -> bool:
    """
    Delete a donor by ID.
    Returns True if deleted, False if not found.
    """
    donor = get_donor(db, donor_id)
    if not donor:
        return False
    db.delete(donor)
    db.commit()
    return True

