import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.healthcare_request import HealthcareRequest
from app.models.healthcare_provider import HealthcareProvider
from app.schemas.healthcare_requests import HealthcareRequestCreate

logger = logging.getLogger(__name__)


async def create_healthcare_request(db: AsyncSession, req: HealthcareRequestCreate, user_id: str):
    """
    Creates a new healthcare request with ownership binding and auto-assignment.
    """
    data = req.model_dump()
    data["user_id"] = user_id  # Enforce data ownership
    data["status"] = "pending"

    provider_id = data.get("assigned_provider_id")

    # Auto-assign if a valid provider ID is provided during creation
    if provider_id and provider_id != 0:
        prov_stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
        prov_result = await db.execute(prov_stmt)
        provider = prov_result.scalars().first()

        if provider:
            data["status"] = "assigned"
            logger.info(f"✅ Auto-assigned {provider.service_type} provider {provider.id} to request.")
        else:
            data["assigned_provider_id"] = None

    obj = HealthcareRequest(**data)
    db.add(obj)
    # Commit handled by the router
    return obj


async def get_healthcare_requests(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        user_id: str = None,
        service_type: Optional[str] = None
):
    """
    Fetches user-owned requests with optional service category filtering.
    """
    # 1. Base query strictly filtered by owner
    query = select(HealthcareRequest).where(HealthcareRequest.user_id == user_id)

    # 2. Unified Filtering Logic (Lab, Pharmacy, Transport, etc.)
    if service_type:
        query = query.where(HealthcareRequest.service_type == service_type)

    stmt = query.order_by(HealthcareRequest.id.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def assign_provider(db: AsyncSession, request_id: int, provider_id: int):
    """
    Assigns a provider to a request with validation.
    """
    req_stmt = select(HealthcareRequest).where(HealthcareRequest.id == request_id)
    req = (await db.execute(req_stmt)).scalars().first()

    prov_stmt = select(HealthcareProvider).where(HealthcareProvider.id == provider_id)
    provider = (await db.execute(prov_stmt)).scalars().first()

    if not req or not provider:
        return None

    # Perform assignment & update status
    req.assigned_provider_id = provider.id
    req.status = "assigned"

    db.add(req)
    # Commit handled by the router
    return req