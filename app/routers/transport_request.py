import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligned with project-standard dependencies
from app.api.dependencies import get_db
from app.schemas.transport_request import TransportRequestCreate, TransportRequest
from app.crud.transport_request import create_transport_request, get_transport_requests

logger = logging.getLogger(__name__)

# --- FIX: Maintained prefix without /v1 to inherit from main.py's v1 router ---
router = APIRouter(
    prefix="/transport-requests",
    tags=["TransportRequests"],
    redirect_slashes=False
)

# -------------------------
# CREATE REQUEST
# -------------------------
@router.post("", response_model=TransportRequest, status_code=status.HTTP_201_CREATED)
async def create_transport(
    req: TransportRequestCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a new transport request (Blood, Emergency, or Patient Transfer).
    Text-based location details are used instead of raw coordinates.
    """
    try:
        # Awaiting the async CRUD logic
        return await create_transport_request(db, req)
    except Exception as e:
        logger.error(f"Failed to create transport request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create transport request"
        )


# -------------------------
# LIST REQUESTS
# -------------------------
@router.get("", response_model=List[TransportRequest])
async def list_transport_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a list of available transport requests for drivers/logistics providers.
    """
    try:
        # Awaiting the async CRUD logic
        return await get_transport_requests(db, skip=skip, limit=limit)
    except Exception as e:
        logger.error(f"Failed to fetch transport requests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch transport requests"
        )