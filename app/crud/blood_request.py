from sqlalchemy.orm import Session
from app.models.blood_request import BloodRequest
from app.schemas.blood_requests import BloodRequestCreate


def create_blood_request(db: Session, req: BloodRequestCreate) -> BloodRequest:
    obj = BloodRequest(
        requester_name=req.requester_name,
        city=req.city,
        phone=req.phone,
        blood_type=req.blood_type,
        hospital=req.hospital,
        latitude=req.latitude,
        longitude=req.longitude,
        urgent=req.urgent,
        needed_units=req.needed_units
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_blood_requests(db: Session, skip: int = 0, limit: int = 100) -> list[BloodRequest]:
    return db.query(BloodRequest).offset(skip).limit(limit).all()
