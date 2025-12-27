# app/routers/transport_offer.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.schemas.transport_offered import TransportOfferCreate, TransportOffer
from app.crud.transport_offer import create_transport_offer, get_transport_offers
from app.dependencies import get_db

router = APIRouter(prefix="/transport-offers", tags=["TransportOffers"])


@router.post("/", response_model=TransportOffer)
def create_transport_offer_endpoint(
    offer: TransportOfferCreate,
    db: Session = Depends(get_db)
):
    try:
        return create_transport_offer(db, offer)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create transport offer") from e


@router.get("/", response_model=List[TransportOffer])
def list_all_transport_offers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db)
):
    try:
        return get_transport_offers(db, skip, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to fetch transport offers") from e
