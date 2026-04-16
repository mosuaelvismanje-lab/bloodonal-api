from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.transport_offer import TransportOffer
from app.schemas.transport_offered import TransportOfferCreate


async def create_transport_offer(db: AsyncSession, offer: TransportOfferCreate) -> TransportOffer:
    """
    Creates a new transport offer asynchronously.
    Uses model_dump() to safely handle the geo-free field structure.
    """
    # ✅ Using model_dump() ensures we only pass fields present in the schema
    # avoiding any "latitude/longitude" attribute errors.
    obj = TransportOffer(**offer.model_dump())
    db.add(obj)

    await db.commit()
    await db.refresh(obj)
    return obj


async def get_transport_offers(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[TransportOffer]:
    """
    Fetches transport offers ordered by newest first using async select.
    """
    # ✅ Optimization: Added id descending order so the most recent
    # transport offers appear at the top of the feed.
    stmt = (
        select(TransportOffer)
        .order_by(TransportOffer.id.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    return result.scalars().all()
