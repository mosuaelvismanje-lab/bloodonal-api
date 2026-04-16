from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.transport_request import TransportRequest
from app.schemas.transport_request import TransportRequestCreate


async def create_transport_request(db: AsyncSession, req: TransportRequestCreate) -> TransportRequest:
    """
    Creates a new transport request asynchronously.
    Matches the geo-free architecture by using .model_dump().
    """
    # ✅ Using model_dump() ensures no crashes from missing lat/lon fields
    obj = TransportRequest(**req.model_dump())
    db.add(obj)

    await db.commit()
    await db.refresh(obj)
    return obj


async def get_transport_requests(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[TransportRequest]:
    """
    Fetches all transport requests ordered by newest first.
    """
    # ✅ Added descending order to prioritize the most recent requests
    stmt = (
        select(TransportRequest)
        .order_by(TransportRequest.id.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    return result.scalars().all()