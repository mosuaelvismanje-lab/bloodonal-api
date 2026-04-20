import logging
from typing import List
from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Project Dependencies
from app.api.dependencies import get_current_user, get_db
from app.schemas.blood_requests import BloodRequestCreate, BloodRequest as BloodRequestOut
from app.crud.blood_request import get_blood_requests
from app.services.blood_request_service import BloodRequestService

# ✅ Unified Logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blood-requests", tags=["BloodRequests"])

# -------------------------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------------------------

@router.post("/", response_model=BloodRequestOut, status_code=status.HTTP_201_CREATED)
async def create_blood_request_endpoint(
    req: BloodRequestCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)  # ✅ ALIGNED: Use unified 'get_db'
):
    """
    Orchestrates blood request creation:
    1. Quota Check (via PaymentService)
    2. Request Persistence
    3. Background Donor Notification
    """
    # Instantiate service with unified session
    blood_service = BloodRequestService(db)

    return await blood_service.create_blood_request_orchestrator(
        req=req,
        user_uid=current_user.uid,
        background_tasks=background_tasks
    )

@router.get("/", response_model=List[BloodRequestOut])
async def list_all_blood_requests(
    skip: int = 0,
    limit: int = 100,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)  # ✅ ALIGNED: Use unified 'get_db'
):
    """Returns a paginated global feed of blood requests."""
    return await get_blood_requests(db, skip=skip, limit=limit)