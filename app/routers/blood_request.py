# app/routers/blood_request.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from app.schemas.blood_requests import BloodRequestCreate, BloodRequest as BloodRequestOut
from app.crud.blood_request import create_blood_request, get_blood_requests  # ensure these are async or call with session
from app.database import get_async_session
from app.models.blood_donor import BloodDonor
from app.firebase_client import send_fcm_to_donor  # sync function using firebase_admin.messaging

router = APIRouter(prefix="/blood-requests", tags=["BloodRequests"])


@router.post("/", response_model=BloodRequestOut, status_code=status.HTTP_201_CREATED)
async def create_blood_request_endpoint(
    req: BloodRequestCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session)
):
    try:
        # If create_blood_request is sync, run in thread; ideally make it async.
        if asyncio.get_event_loop().is_running():
            # assume create_blood_request is synchronous and expects a Session; use to_thread
            br = await asyncio.to_thread(create_blood_request, db, req)
        else:
            br = create_blood_request(db, req)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not save blood request")

    # Fetch eligible donors (async query)
    q = await db.execute(
        select(BloodDonor)
        .where(
            BloodDonor.blood_type == req.blood_type,
            BloodDonor.is_active.is_(True),
            BloodDonor.fcm_token.isnot(None)
        )
    )
    donors = q.scalars().all()

    title = f"{'Urgent' if req.urgent else 'New'} {req.blood_type} blood needed"
    body = f"{req.requester_name} needs {req.needed_units} unit(s) of blood in {req.city} at {req.hospital or 'a hospital nearby'}"

    # Schedule FCM sends on background thread
    for donor in donors:
        # schedule send_fcm_to_donor(donor.fcm_token, title, body) on background thread
        background_tasks.add_task(asyncio.to_thread, send_fcm_to_donor, donor.fcm_token, title, body)

    return br


@router.get("/", response_model=list[BloodRequestOut])
async def list_all_blood_requests(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session)):
    # ensure get_blood_requests is async; otherwise run in thread
    return await get_blood_requests(db, skip=skip, limit=limit)
