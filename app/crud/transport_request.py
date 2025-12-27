# app/crud/transport_request.py
from sqlalchemy.orm import Session
from app.models.transport_request import TransportRequest
from app.schemas.transport_request import TransportRequestCreate

def create_transport_request(db: Session, req: TransportRequestCreate):
    obj = TransportRequest(**req.dict())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_transport_requests(db: Session, skip: int = 0, limit: int = 100):
    return db.query(TransportRequest).offset(skip).limit(limit).all()
