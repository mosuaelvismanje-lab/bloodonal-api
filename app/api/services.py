import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db, get_redis
from app.models.service_listing import ServiceListing
from app.services.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/services",
    tags=["Service Fulfillment"],
)


@router.post("/accept/{request_id}")
async def accept_service(
    request_id: uuid.UUID,
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    """
    Atomically assigns a service request to a provider using a distributed lock.
    """

    # 1) Fetch listing
    listing = await db.get(ServiceListing, request_id)
    if not listing or not listing.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service request not found or not yet published.",
        )

    # 2) Registry validation
    try:
        service_meta = registry.get_service_meta(listing.service_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # 3) Acquire distributed lock
    lock_key = f"lock:request:{request_id}"
    lock_token = f"{provider_id}:{uuid.uuid4().hex[:6]}"

    try:
        is_locked = await redis.set(lock_key, lock_token, nx=True, ex=10)
    except Exception as e:
        logger.error("❌ Redis lock failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not process request at the moment.",
        )

    if not is_locked:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another provider is already accepting this request.",
        )

    try:
        # 4) Atomic DB update
        stmt = (
            update(ServiceListing)
            .where(
                ServiceListing.id == request_id,
                ServiceListing.status == "PENDING",
                ServiceListing.provider_id.is_(None),
            )
            .values(
                provider_id=provider_id,
                status="ASSIGNED",
                accepted_at=datetime.now(timezone.utc),
            )
            .returning(ServiceListing.id)
        )

        result = await db.execute(stmt)
        updated_id = result.scalar_one_or_none()

        if not updated_id:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Too late! Request already assigned.",
            )

        await db.commit()

        return {
            "status": "success",
            "service": service_meta.get("display_name", listing.service_type),
            "message": "You have successfully accepted the request.",
        }

    except HTTPException:
        raise

    except Exception as e:
        await db.rollback()
        logger.error(
            "❌ Error accepting service %s: %s",
            request_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign request due to a server error.",
        )

    finally:
        # 5) Safe lock release
        try:
            current_token = await redis.get(lock_key)

            if current_token is not None:
                if isinstance(current_token, bytes):
                    current_token = current_token.decode()

                if current_token == lock_token:
                    await redis.delete(lock_key)

        except Exception as e:
            logger.warning("⚠️ Failed to release Redis lock: %s", e)