# app/crud/transport_offer.py
from sqlalchemy.orm import Session
from app.models.transport_offer import TransportOffer
from app.schemas.transport_offered import TransportOfferCreate

def create_transport_offer(db: Session, offer: TransportOfferCreate):
    obj = TransportOffer(**offer.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def get_transport_offers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(TransportOffer).offset(skip).limit(limit).all()
