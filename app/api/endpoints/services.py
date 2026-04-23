import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_current_user, get_redis
from app.models import ServiceListing
from app.schemas.serviceschema import ServiceListingResponse, ServiceAcceptRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/services", tags=["Services"])


# -------------------------------------------------
# 1. DISCOVERY FEED
# -------------------------------------------------
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
        ServiceListing.is_published.is_(True),
    ).order_by(ServiceListing.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


# -------------------------------------------------
# 2. SERVICE ACCEPTANCE (ATOMIC + REDIS SAFE)
# -------------------------------------------------
@router.post("/accept/{listing_id}")
async def accept_service(
    listing_id: uuid.UUID,
    payload: ServiceAcceptRequest,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
    current_user=Depends(get_current_user),
):
    """
    Atomic acceptance of a service listing using Redis lock.
    """

    lock_key = f"lock:listing:{listing_id}"
    lock_token = f"{current_user.uid}:{uuid.uuid4().hex[:6]}"

    # 1) Redis lock
    try:
        is_locked = await redis.set(lock_key, lock_token, nx=True, ex=10)
    except Exception as e:
        logger.error("Redis lock failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable."
        )

    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already accepted by another provider."
        )

    try:
        # 2) Atomic DB update
        stmt = (
            update(ServiceListing)
            .where(
                ServiceListing.id == listing_id,
                ServiceListing.status == "PENDING",
                ServiceListing.provider_id.is_(None),
            )
            .values(
                status="ACCEPTED",
                provider_id=current_user.uid
            )
            .returning(ServiceListing.id)
        )

        result = await db.execute(stmt)
        updated_id = result.scalar_one_or_none()

        if not updated_id:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Listing already taken or expired."
            )

        await db.commit()

        return {
            "status": "success",
            "message": "Service accepted successfully",
            "listing_id": str(updated_id),
        }

    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        logger.error("Acceptance failure: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transaction failed."
        )

    finally:
        # 3) Safe lock release
        try:
            current_value = await redis.get(lock_key)

            if current_value is not None:
                if isinstance(current_value, bytes):
                    current_value = current_value.decode()

                if current_value == lock_token:
                    await redis.delete(lock_key)

        except Exception as e:
            logger.warning("Redis lock cleanup failed: %s", e)