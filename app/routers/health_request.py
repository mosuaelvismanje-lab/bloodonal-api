import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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

# ✅ Versioning: Prefix set to /v1 to match production API layout
router = APIRouter(prefix="/v1/healthcare-requests", tags=["HealthcareRequests"])


@router.post("/", response_model=HealthcareRequest, status_code=status.HTTP_201_CREATED)
async def create(
        req: HealthcareRequestCreate,
        db: AsyncSession = Depends(get_db_session),
        current_user = Depends(get_current_user) # ✅ Secure Identity
):
    """
    Creates a healthcare request linked to the authenticated user.
    """
    try:
        # Pass current_user.uid to the CRUD to ensure ownership
        new_request = await create_healthcare_request(db, req, user_id=current_user.uid)
        await db.commit() # ✅ Persistence required for AsyncSession
        await db.refresh(new_request)
        return new_request
    except IntegrityError as exc:
        await db.rollback()
        logger.warning(f"Integrity Error for user {current_user.uid}: {str(exc)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid provider selected. Please select a valid provider."
        )
    except Exception as exc:
        await db.rollback()
        logger.exception(f"Failed to create request for {current_user.uid}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not process healthcare request"
        )


@router.get("/", response_model=List[HealthcareRequest])
async def list_all(
        skip: int = 0,
        limit: int = 100,
        db: AsyncSession = Depends(get_db_session),
        current_user = Depends(get_current_user)
):
    """
    Returns a list of requests. In production, this usually filters
    by current_user.uid unless the user is an admin.
    """
    try:
        return await get_healthcare_requests(db, skip, limit)
    except Exception as exc:
        logger.exception("Failed to list healthcare requests")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve requests"
        )


@router.put("/{request_id}/assign/{provider_id}", response_model=HealthcareRequest)
async def assign(
        request_id: int,
        provider_id: int,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db_session),
        current_user = Depends(get_current_user)
):
    """
    Manually assign a provider. Triggers status update to 'assigned'.
    """
    try:
        # 1. Verify provider existence
        provider = await get_provider_by_id(db, provider_id)
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Provider not found"
            )

        # 2. Perform assignment
        obj = await assign_provider(db, request_id, provider_id)
        if not obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Healthcare request not found"
            )

        await db.commit()
        await db.refresh(obj)

        # ✅ Background Task (e.g., FCM Notification to Provider)
        # background_tasks.add_task(notify_provider_of_assignment, provider, obj)

        logger.info(f"Request {request_id} assigned to {provider_id} by {current_user.uid}")
        return obj

    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("Failed to assign provider")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during provider assignment"
        )