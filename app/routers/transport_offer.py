import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Standardized imports
from app.api.dependencies import get_db
from app.schemas.transport_offered import TransportOfferCreate, TransportOffer
from app.crud.transport_offer import create_transport_offer, get_transport_offers

logger = logging.getLogger(__name__)

# --- FIX: Removed '/v1' prefix to inherit from main.py ---
router = APIRouter(
    prefix="/transport-offers",
    tags=["TransportOffers"]
)

#  CREATE OFFER
@router.post("", response_model=TransportOffer, status_code=status.HTTP_201_CREATED)
async def create_transport_offer_endpoint(
    offer: TransportOfferCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new transport offer.
    """
    try:
        return await create_transport_offer(db, offer)
    except Exception as e:
        logger.error(f"Error creating transport offer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create transport offer"
        )

#  LIST OFFERS
@router.get("", response_model=List[TransportOffer])
async def list_all_transport_offers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a list of available transport offers.
    """
    try:
        return await get_transport_offers(db, skip, limit)
    except Exception as e:
        logger.error(f"Error fetching transport offers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch transport offers"
        )