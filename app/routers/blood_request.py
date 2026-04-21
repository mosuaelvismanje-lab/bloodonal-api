import logging
from typing import List

from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Dependencies
from app.api.dependencies import get_current_user, get_db

# ✅ Schemas
from app.schemas.blood_requests import BloodRequestCreate, BloodRequest as BloodRequestOut

# ✅ CRUD
from app.crud.blood_request import get_blood_requests

# ✅ Service Layer
from app.services.blood_request_service import BloodRequestService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/blood-requests",
    tags=["BloodRequests"],
    redirect_slashes=False
)

# -------------------------------------------------------------------------
# CREATE BLOOD REQUEST (ORCHESTRATED FLOW)
# -------------------------------------------------------------------------
@router.post(
    "/",
    response_model=BloodRequestOut,
    status_code=status.HTTP_201_CREATED
)
async def create_blood_request_endpoint(
    req: BloodRequestCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Orchestrates blood request creation:

    1. Payment/Quota check via PaymentService
    2. If FREE → persist request + activate service
    3. If PAID → return USSD response immediately
    4. Background notification to donors
    """

    blood_service = BloodRequestService(db)

    return await blood_service.create_request_orchestrator(
        req=req,
        user_uid=current_user.uid,
        background_tasks=background_tasks
    )


# -------------------------------------------------------------------------
# LIST BLOOD REQUESTS
# -------------------------------------------------------------------------
@router.get(
    "/",
    response_model=List[BloodRequestOut]
)
async def list_all_blood_requests(
    skip: int = 0,
    limit: int = 100,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns global blood request feed (paginated).
    """

    return await get_blood_requests(db, skip=skip, limit=limit)