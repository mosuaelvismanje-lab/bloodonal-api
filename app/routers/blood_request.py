import logging
import asyncio
from typing import List

from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Dependencies & Schemas
from app.api.dependencies import get_current_user, get_db as get_db_session
from app.schemas.blood_requests import BloodRequestCreate, BloodRequest as BloodRequestOut
from app.crud.blood_request import get_blood_requests
from app.models.blood_donor import BloodDonor
from app.firebase_client import send_fcm_to_donor

# Modular Service Link
from app.services.blood_request_service import BloodRequestService

# ✅ Structured logger for the Blood Request module
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blood-requests", tags=["BloodRequests"])


# -------------------------------------------------------------------------
# BACKGROUND TASK: ASYNC NOTIFICATION ENGINE
# -------------------------------------------------------------------------
async def notify_donors_background(req_data: BloodRequestCreate, request_id: str):
    """
    Background worker to match donors by blood type/location and dispatch FCM.
    Note: Can be moved to app/services/notification_service.py for higher modularity.
    """
    from app.database import AsyncSessionLocal  # Local import to prevent circular dependency

    async with AsyncSessionLocal() as db:
        try:
            # 1. Efficiently query active donors with tokens
            query = select(BloodDonor).where(
                BloodDonor.blood_type == req_data.blood_type,
                BloodDonor.city == req_data.city,
                BloodDonor.is_active == True,
                BloodDonor.fcm_token.isnot(None)
            )
            result = await db.execute(query)
            donors = result.scalars().all()

            if not donors:
                logger.info(f"MATCH_EMPTY: [Req {request_id}] No matching donors in {req_data.city}.")
                return

            # 2. Build Notification Content
            urgency_prefix = "🚨 URGENT:" if req_data.urgent else "New"
            title = f"{urgency_prefix} {req_data.blood_type} Needed"
            body = (f"{req_data.requester_name} needs {req_data.needed_units} unit(s) "
                    f"at {req_data.hospital or req_data.city}")

            # 3. Concurrent thread-safe dispatch
            for donor in donors:
                # Use to_thread for blocking Firebase Admin SDK calls
                await asyncio.to_thread(
                    send_fcm_to_donor,
                    donor.fcm_token,
                    title,
                    body,
                    {"type": "BLOOD_REQUEST_ALERT", "request_id": str(request_id)}
                )

            logger.info(f"MATCH_SUCCESS: [Req {request_id}] Alerts sent to {len(donors)} donors.")

        except Exception as e:
            logger.error(f"MATCH_ERROR: [Req {request_id}] Notification failed: {str(e)}", exc_info=True)


# -------------------------------------------------------------------------
# ENDPOINTS
# -------------------------------------------------------------------------

@router.post("/", response_model=BloodRequestOut, status_code=status.HTTP_201_CREATED)
async def create_blood_request_endpoint(
    req: BloodRequestCreate,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new blood request.
    Orchestration (Quota checks, DB persistence, Notification triggers)
    is handled by BloodRequestService.
    """
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
    db: AsyncSession = Depends(get_db_session)
):
    """Returns a paginated global feed of blood requests."""
    return await get_blood_requests(db, skip=skip, limit=limit)