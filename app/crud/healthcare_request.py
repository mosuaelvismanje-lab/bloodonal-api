from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.healthcare_request import HealthcareRequest
from app.models.healthcare_provider import HealthcareProvider
from app.schemas.healthcare_requests import HealthcareRequestCreate
import logging

logger = logging.getLogger(__name__)


async def create_healthcare_request(db: AsyncSession, req: HealthcareRequestCreate):
    """
    Creates a new healthcare request.
    Logic: If a valid provider is found, status = 'assigned'.
    If ID is 0 or not found, status = 'pending'.
    """
    data = req.model_dump()
    provider_id = data.get("assigned_provider_id")

    # ✅ Step 1: Default to Pending
    data["status"] = "pending"

    # ✅ Step 2: Safety Gate & Auto-Status Update
    if provider_id and provider_id != 0:
        prov_stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
        prov_result = await db.execute(prov_stmt)
        provider = prov_result.scalars().first()

        if provider:
            # If provider is found during creation, set to assigned immediately
            data["assigned_provider_id"] = provider.id
            data["status"] = "assigned"
            logger.info(f"Auto-assigned Provider {provider.id} to new request.")
        else:
            # If ID was sent but not found in DB, reset to None
            data["assigned_provider_id"] = None
    else:
        data["assigned_provider_id"] = None

    obj = HealthcareRequest(**data)
    db.add(obj)

    try:
        await db.commit()
        await db.refresh(obj)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create request: {e}")
        raise

    return obj


async def get_healthcare_requests(db: AsyncSession, skip: int = 0, limit: int = 100):
    """
    Fetches requests ordered by most recent.
    """
    stmt = (
        select(HealthcareRequest)
        .order_by(HealthcareRequest.id.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def assign_provider(db: AsyncSession, request_id: int, provider_id: int):
    """
    Manual Assignment Logic:
    Updates status to 'assigned' and can be extended to 'on_route'.
    """
    # 1. Fetch the request
    req_stmt = select(HealthcareRequest).where(HealthcareRequest.id == request_id)
    req_result = await db.execute(req_stmt)
    req = req_result.scalars().first()

    if not req:
        return None

    # 2. Fetch the provider
    prov_stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    prov_result = await db.execute(prov_stmt)
    provider = prov_result.scalars().first()

    if not provider:
        return None

    # 3. Validation
    # Ensure the service type is appropriate for medical requests
    valid_types = {"doctor", "nurse", "lab", "ambulance"}
    if provider.service_type and provider.service_type.value.lower() not in valid_types:
        logger.warning(f"Provider {provider_id} type {provider.service_type} is not valid for assignment.")
        return None

    # 4. Perform assignment & Automatic Status Update
    req.assigned_provider_id = provider.id

    # ✅ Logic Update: You can change this to "on_route" if your frontend
    # needs to show the provider is moving immediately.
    req.status = "assigned"

    db.add(req)
    try:
        await db.commit()
        await db.refresh(req)
        logger.info(f"Request {request_id} successfully updated to 'assigned' status.")
    except Exception as e:
        await db.rollback()
        logger.error(f"Assignment commit failed: {e}")
        raise

    return req