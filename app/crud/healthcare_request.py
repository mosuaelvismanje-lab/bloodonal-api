from sqlalchemy.orm import Session
from app.models.healthcare_request import HealthcareRequest
from app.models.healthcare_provider import HealthcareProvider
from app.schemas.healthcare_requests import HealthcareRequestCreate

def create_healthcare_request(db: Session, req: HealthcareRequestCreate):
    obj = HealthcareRequest(**req.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_healthcare_requests(db: Session, skip: int = 0, limit: int = 100):
    return db.query(HealthcareRequest).offset(skip).limit(limit).all()

def assign_provider(db: Session, request_id: int, provider_id: int):
    req = db.query(HealthcareRequest).filter_by(id=request_id).first()
    if not req:
        return None

    provider = db.query(HealthcareProvider).filter_by(id=provider_id).first()
    if not provider:
        return None  # provider does not exist

    # Optional: only allow assignment to valid service types
    if provider.service_type not in ("doctor", "nurse", "lab"):
        return None

    req.assigned_provider_id = provider.id
    req.status = "assigned"
    db.commit()
    db.refresh(req)
    return req
