import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

# ✅ Standards-aligned Dependencies
from app.api.dependencies import get_db_session, get_current_user
from app.schemas.healthcare_requests import HealthcareRequest, HealthcareRequestCreate
from app.crud.healthcare_request import (
    create_healthcare_request,
    get_healthcare_requests,
    assign_provider,
)
from app.crud.healthcare_provider import get_provider_by_id

logger = logging.getLogger(__name__)

# ✅ Unified Gateway for all healthcare service requests
router = APIRouter(prefix="/healthcare-requests", tags=["HealthcareRequests"])

# -------------------------------------------------
# CREATE REQUEST
# -------------------------------------------------
@router.post("/", response_model=HealthcareRequest, status_code=status.HTTP_201_CREATED)
async def create(
        req: HealthcareRequestCreate,
        db: AsyncSession = Depends(get_db_session),
        current_user = Depends(get_current_user)
):
    """
    Creates a unified healthcare request (e.g., Doctor, Nurse, Lab, Transport).
    """
    try:
        new_request = await create_healthcare_request(db, req, user_id=current_user.uid)
        await db.commit()
        await db.refresh(new_request)
        logger.info(f"✅ Created {req.service_type} request {new_request.id} for user {current_user.uid}")
        return new_request
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(f"⚠️ Integrity error for user {current_user.uid}: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not create request. Verify provider selection."
        )
    except Exception:
        await db.rollback()
        logger.exception(f"❌ Critical failure creating request for user {current_user.uid}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing request"
        )

# -------------------------------------------------
# LIST REQUESTS (WITH OPTIONAL TYPE FILTER)
# -------------------------------------------------
@router.get("/", response_model=List[HealthcareRequest])
async def list_all(
        skip: int = 0,
        limit: int = 100,
        service_type: Optional[str] = Query(None, description="Filter requests by category (e.g., Lab, Transport)"),
        db: AsyncSession = Depends(get_db_session),
        current_user = Depends(get_current_user)
):
    """
    Returns a list of user requests, optionally filtered by service_type.
    """
    try:
        return await get_healthcare_requests(
            db, skip=skip, limit=limit, user_id=current_user.uid, service_type=service_type
        )
    except Exception:
        logger.exception(f"❌ Failed to list healthcare requests for {current_user.uid}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve your healthcare requests"
        )

# -------------------------------------------------
# ASSIGN PROVIDER
# -------------------------------------------------
@router.put("/{request_id}/assign/{provider_id}", response_model=HealthcareRequest)
async def assign(
        request_id: int,
        provider_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user = Depends(get_current_user)
):
    """
    Assigns a verified provider to a specific healthcare request.
    """
    try:
        provider = await get_provider_by_id(db, provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")

        obj = await assign_provider(db, request_id, provider_id)
        if not obj:
            raise HTTPException(status_code=404, detail="Healthcare request not found")

        await db.commit()
        await db.refresh(obj)
        logger.info(f"✅ Request {request_id} assigned to provider {provider_id}")
        return obj
    except HTTPException:
        raise
    except Exception:
        await db.rollback()
        logger.exception(f"❌ Failed assignment for request {request_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during provider assignment"
        )