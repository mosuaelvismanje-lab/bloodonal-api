import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

# Project-standard imports
from app.schemas.transport_request import TransportRequestCreate, TransportRequest
from app.crud.transport_request import create_transport_request, get_transport_requests
from app.database import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transport-requests", tags=["TransportRequests"])

# --- UPDATES MADE ---
# 1. Converted all endpoints to 'async def'
# 2. Switched 'Session' to 'AsyncSession'
# 3. Replaced 'get_db' with 'get_async_session'
# 4. Added logging and proper HTTP status codes

#  CREATE REQUEST
@router.post("/", response_model=TransportRequest, status_code=status.HTTP_201_CREATED)
async def create_transport(
    req: TransportRequestCreate,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Submit a new transport request.
    Pickup/Dropoff coordinates have been removed in favor of text details.
    """
    try:
        # Direct await of the async CRUD function
        return await create_transport_request(db, req)
    except Exception as e:
        logger.error(f"Failed to create transport request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create transport request"
        )


#  LIST REQUESTS
@router.get("/", response_model=List[TransportRequest])
async def list_transport_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Retrieve a list of transport requests.
    """
    try:
        # Direct await of the async CRUD function
        return await get_transport_requests(db, skip=skip, limit=limit)
    except Exception as e:
        logger.error(f"Failed to fetch transport requests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not fetch transport requests"
        )