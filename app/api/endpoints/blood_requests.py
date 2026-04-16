from __future__ import annotations

import logging
import asyncio
from typing import List

from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Standards-aligned Dependencies
from app.api.dependencies import get_current_user, get_db as get_db_session
from app.schemas.blood_requests import BloodRequestCreate, BloodRequest as BloodRequestOut
from app.crud.blood_request import get_blood_requests
from app.models.blood_donor import BloodDonor
from app.firebase_client import send_fcm_to_donor

# ✅ The Modular Service Linker
from app.services.blood_request_service import BloodRequestService

logger = logging.getLogger(__name__)

# Standardized prefix for the API gateway
router = APIRouter(prefix="/blood-requests", tags=["BloodRequests"])


# -------------------------------------------------------------------------
# BACKGROUND TASK: ASYNC NOTIFICATION ENGINE
# -------------------------------------------------------------------------
async def notify_donors_background(req_data: BloodRequestCreate, request_id: str):
    """
    Handles donor lookup and FCM dispatch using thread pooling for blocking SDK calls.
    Optimized for 2026 to handle concurrent notification bursts.
    """
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            # Match donors by blood type and location
            query = select(BloodDonor).where(
                BloodDonor.blood_type == req_data.blood_type,
                BloodDonor.city == req_data.city,
                BloodDonor.is_active == True,
                BloodDonor.fcm_token.isnot(None)
            )
            result = await db.execute(query)
            donors = result.scalars().all()

            if not donors:
                logger.info(f"[{request_id}] No donors found for {req_data.blood_type} in {req_data.city}")
                return

            title = f"{'🚨 Urgent:' if req_data.urgent else 'New'} {req_data.blood_type} needed"
            body = f"{req_data.requester_name} needs {req_data.needed_units} unit(s) at {req_data.hospital or req_data.city}"

            # ✅ 2026 Optimization: Fire notifications in parallel
            # This prevents a long list of donors from blocking the background worker
            tasks = [
                asyncio.to_thread(
                    send_fcm_to_donor,
                    donor.fcm_token,
                    title,
                    body,
                    {"type": "BLOOD_REQUEST_ALERT", "request_id": str(request_id)}
                )
                for donor in donors
            ]

            await asyncio.gather(*tasks)

            logger.info(f"[{request_id}] Notifications sent to {len(donors)} donors.")

        except Exception as e:
            logger.error(f"[{request_id}] Notification background task failed: {e}")


# -------------------------------------------------------------------------
# POST: CREATE BLOOD REQUEST
# -------------------------------------------------------------------------
@router.post("/", response_model=BloodRequestOut, status_code=status.HTTP_201_CREATED)
async def create_blood_request_endpoint(
        req: BloodRequestCreate,
        background_tasks: BackgroundTasks,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """
    Entry point for mobile blood requests.
    Logic Flow:
    1. Authenticates user via Firebase.
    2. Hands execution to BloodRequestService for quota/validation/storage.
    3. Service triggers notifications in background_tasks.
    """
    blood_service = BloodRequestService(db)

    # Returns the created request and schedules notify_donors_background via the service
    return await blood_service.create_request_process(
        req=req,
        user_uid=current_user.uid,
        background_tasks=background_tasks
    )


# -------------------------------------------------------------------------
# GET: LIST ALL REQUESTS
# -------------------------------------------------------------------------
@router.get("/", response_model=List[BloodRequestOut])
async def list_all_blood_requests(
        skip: int = 0,
        limit: int = 100,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """Returns a global feed of active blood requests for the mobile app."""
    return await get_blood_requests(db, skip=skip, limit=limit)