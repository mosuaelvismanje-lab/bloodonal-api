import logging
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select

# ✅ Standard Dependencies
from app.database import get_db
from app.core.redis import get_redis_client

# ✅ Service & Model Logic
from app.services.registry import registry
from app.models.service_listing import ServiceListing

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/services",
    tags=["Service Fulfillment"],
)


@router.post("/accept/{request_id}")
async def accept_service(
        request_id: uuid.UUID,  # ✅ Changed to UUID for DB compatibility
        provider_id: uuid.UUID, # ✅ Changed to UUID for type-safety
        db: AsyncSession = Depends(get_db),
        redis=Depends(get_redis_client)
):
    """
    Atomically assigns a service request to a provider using distributed locking.
    """

    # 1️⃣ Pre-Check: Fetch the listing
    listing = await db.get(ServiceListing, request_id)
    if not listing or not listing.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found or not yet published."
        )

    # 2️⃣ Registry Validation
    try:
        service_meta = registry.get_service_meta(listing.service_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # 3️⃣ Distributed Locking (Redis)
    # Prevents multiple providers from triggering the DB update simultaneously
    lock_key = f"lock:request:{request_id}"
    lock_token = f"{provider_id}:{uuid.uuid4().hex[:6]}"

    # NX=True ensures only one client can set this key; EX=10 sets a 10s timeout
    is_locked = await redis.set(lock_key, lock_token, nx=True, ex=10)

    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Someone else is already accepting this request."
        )

    try:
        # 4️⃣ Atomic Database Update
        # We check provider_id == None inside the 'where' clause as a secondary guard
        stmt = (
            update(ServiceListing)
            .where(
                ServiceListing.id == request_id,
                ServiceListing.provider_id == None
            )
            .values(
                provider_id=provider_id,
                status="ASSIGNED",
                accepted_at=datetime.now(timezone.utc) # ✅ Works now with import
            )
            .returning(ServiceListing.id)
        )

        result = await db.execute(stmt)
        updated_id = result.scalar_one_or_none()

        if not updated_id:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Too late! Request already assigned."
            )

        await db.commit()

        return {
            "status": "success",
            "service": service_meta.get("display_name", listing.service_type),
            "message": f"You have successfully accepted the request."
        }

    except HTTPException:
        raise  # Re-raise FastAPI exceptions (410, etc.)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error accepting service {request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign request due to a server error."
        )

    finally:
        # 5️⃣ Safe Lock Release
        # Only delete the lock if we are the ones who set it
        current_token = await redis.get(lock_key)
        # Redis returns bytes, so we decode or compare carefully
        if current_token and (current_token.decode() if isinstance(current_token, bytes) else current_token) == lock_token:
            await redis.delete(lock_key)