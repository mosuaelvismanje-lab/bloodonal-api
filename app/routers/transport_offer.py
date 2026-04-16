import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

# Standardized imports across your project
from app.schemas.transport_offered import TransportOfferCreate, TransportOffer
from app.crud.transport_offer import create_transport_offer, get_transport_offers
from app.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transport-offers", tags=["TransportOffers"])

# --- UPDATES MADE ---
# 1. Switched from sync 'Session' to 'AsyncSession'
# 2. Used 'get_async_session' to match your Neon database setup
# 3. Converted endpoints to 'async def' and 'await' CRUD calls
# 4. Added proper status codes and logging

#  CREATE OFFER
@router.post("/", response_model=TransportOffer, status_code=status.HTTP_201_CREATED)
async def create_transport_offer_endpoint(
    offer: TransportOfferCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Create a new transport offer.
    Note: Latitude and Longitude are no longer required.
    """
    try:
        # Directly await the async CRUD function
        return await create_transport_offer(db, offer)
    except Exception as e:
        logger.error(f"Error creating transport offer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create transport offer"
        )

#  LIST OFFERS
@router.get("/", response_model=List[TransportOffer])
async def list_all_transport_offers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Retrieve a list of available transport offers.
    """
    try:
        # Directly await the async CRUD function
        return await get_transport_offers(db, skip, limit)
    except Exception as e:
        logger.error(f"Error fetching transport offers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch transport offers"
        )