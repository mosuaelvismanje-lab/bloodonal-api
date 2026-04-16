from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.database import get_db
from app.models.servicemodel import ServiceRequest
from app.schemas.serviceschema import ServiceRequestResponse, ServiceAcceptRequest
from typing import List

# Import your redis client (Update path based on where you put it)
from app.core.redis import get_redis_connection

router = APIRouter()


# --- DISCOVERY FEED ---
@router.get("/available", response_model=List[ServiceRequestResponse])
async def get_available_services(
        service_type: str,
        city: str,
        db: AsyncSession = Depends(get_db)
):
    """Fetch pending requests for a specific service and city."""
    query = select(ServiceRequest).where(
        ServiceRequest.service_type == service_type,
        ServiceRequest.city == city,
        ServiceRequest.status == "PENDING"
    ).order_by(ServiceRequest.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


# --- SERVICE ACCEPTANCE (The Real-time Part) ---
@router.post("/accept/{request_id}")
async def accept_service(
        request_id: int,
        provider_id: str,  # From Firebase Auth UID
        db: AsyncSession = Depends(get_db),
        redis=Depends(get_redis_connection)
):
    """Atomically accept a request using Memurai as a distributed lock."""
    lock_key = f"lock:service:{request_id}"

    # 1. Try to set the lock in Memurai (nx=True means 'only if not exists')
    # If this fails, someone already accepted it.
    is_locked = redis.set(lock_key, provider_id, nx=True, ex=10)

    if not is_locked:
        raise HTTPException(status_code=409, detail="Request already accepted by another provider.")

    try:
        # 2. Update the Database
        stmt = update(ServiceRequest).where(
            ServiceRequest.id == request_id,
            ServiceRequest.status == "PENDING"
        ).values(
            status="ACCEPTED",
            accepted_by=provider_id
        )

        result = await db.execute(stmt)
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=400, detail="Request is no longer pending.")

        return {"status": "success", "message": "Service accepted successfully"}

    except Exception as e:
        await db.rollback()
        redis.delete(lock_key)  # Release lock on failure
        raise HTTPException(status_code=500, detail=str(e))