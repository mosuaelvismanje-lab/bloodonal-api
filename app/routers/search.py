import logging
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Aligned Dependencies
from app.api.dependencies import get_db
from app.models import User, ServiceListing
from app.schemas.search import SearchItem

logger = logging.getLogger(__name__)

# --- FIX: Removed '/api/v1' from prefix ---
router = APIRouter(
    prefix="/search",
    tags=["Search"]
)


@router.get("", response_model=List[SearchItem])
async def global_search(
        q: str = Query(..., min_length=1),
        db: AsyncSession = Depends(get_db)
):
    """
    Search across multiple modules (Healthcare, Transport, Blood)
    Optimized with SQLAlchemy Async.
    """
    try:
        search_pattern = f"%{q}%"

        # 1. Search Users (Async)
        user_stmt = select(User).where(User.full_name.ilike(search_pattern))
        users_result = await db.execute(user_stmt)
        users = users_result.scalars().all()

        # 2. Search Services (Async)
        service_stmt = select(ServiceListing).where(ServiceListing.service_name.ilike(search_pattern))
        services_result = await db.execute(service_stmt)
        services = services_result.scalars().all()

        combined_results = []

        # Map Users to SearchItem
        for u in users:
            combined_results.append(SearchItem(
                id=str(u.id),
                title=u.full_name,
                subtitle=u.role.capitalize(),
                type=u.role.lower(),
                imageUrl=u.profile_image,
                category=u.role
            ))

        # Map Services to SearchItem
        for s in services:
            combined_results.append(SearchItem(
                id=str(s.id),
                title=s.service_name,
                subtitle=s.category.upper(),
                type=s.category.lower(),
                imageUrl=s.icon_url,
                category=s.category
            ))

        return combined_results

    except Exception as e:
        logger.error(f"Global search failed for query '{q}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search service temporarily unavailable"
        )