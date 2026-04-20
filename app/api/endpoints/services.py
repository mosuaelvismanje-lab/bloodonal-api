import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List

# ✅ Project Dependencies
from app.api.dependencies import get_db, get_current_user
from app.models import ServiceListing

from app.schemas.serviceschema import ServiceListingResponse, ServiceAcceptRequest
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["Services"])

# --- DISCOVERY FEED ---
@router.get("/available", response_model=List[ServiceListingResponse])
async def get_available_services(
        service_type: str,
        city: str,
        db: AsyncSession = Depends(get_db)
):
    """Fetch pending listings for a specific service and city."""
    query = select(ServiceListing).where(
        ServiceListing.service_type == service_type,
        ServiceListing.location_city == city,
        ServiceListing.status == "PENDING",
        ServiceListing.is_published == True
    ).order_by(ServiceListing.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


# --- SERVICE ACCEPTANCE (Aligned with Async Redis) ---
@router.post("/accept/{listing_id}")
async def accept_service(
        listing_id: str,
        payload: ServiceAcceptRequest,
        db: AsyncSession = Depends(get_db),
        redis=Depends(get_redis_client), # Aligned function name
        current_user=Depends(get_current_user)
):
    """
    Atomic acceptance of a polymorphic listing using async Redis.
    """
    lock_key = f"lock:listing:{listing_id}"

    # 1. Distributed Lock (Must be awaited)
    # nx=True and ex=10 are standard arguments for redis-py
    is_locked = await redis.set(lock_key, current_user.uid, nx=True, ex=10)

    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already accepted by another provider."
        )

    try:
        # 2. Update the Polymorphic Listing
        stmt = update(ServiceListing).where(
            ServiceListing.id == listing_id,
            ServiceListing.status == "PENDING"
        ).values(
            status="ACCEPTED",
            provider_id=current_user.uid
        )

        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=400, detail="Listing no longer available.")

        return {"status": "success", "message": "Service accepted successfully"}

    except Exception as e:
        await db.rollback()
        # Ensure lock is released even on DB failure
        await redis.delete(lock_key)
        logger.error(f"Acceptance failure: {e}")
        raise HTTPException(status_code=500, detail="Transaction failed.")