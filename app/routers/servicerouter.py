from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

# ✅ Updated Modular Imports
# Points to service_listing.py where ServiceUser and ServiceListing live
from app.models.service_listing import ServiceUser, ServiceListing
from app.schemas import serviceschema
from app.db.session import get_db

log = logging.getLogger("bloodonal")

router = APIRouter(prefix="/services", tags=["Service Stack"])


@router.get("/search", response_model=List[serviceschema.SearchItemOut])
async def global_modular_search(
        q: str = Query(..., min_length=2, description="Search by name, role, or request title"),
        limit: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db)
):
    """
    ### 2026 High-Performance Global Search
    This endpoint performs a dual-layer asynchronous search across:
    1. **Service Providers:** Profiles of actors (Doctors, Donors, etc.)
    2. **Service Listings:** The polymorphic requests (Blood, Taxi, etc.)

    Uses **Async SQLAlchemy 2.0** and the consolidated ServiceListing model.
    """
    search_pattern = f"%{q}%"
    results = []

    try:
        # --- LAYER 1: PROVIDER SEARCH (ServiceUser) ---
        provider_stmt = (
            select(ServiceUser)
            .where(
                or_(
                    ServiceUser.full_name.ilike(search_pattern),
                    ServiceUser.role.ilike(search_pattern),
                    ServiceUser.city.ilike(search_pattern)
                )
            )
            .limit(limit)
        )

        provider_res = await db.execute(provider_stmt)
        providers = provider_res.scalars().all()

        for p in providers:
            results.append(serviceschema.SearchItemOut(
                id=str(p.id),
                title=p.full_name,
                subtitle=f"Verified {p.role.title()} in {p.city}",
                type="provider",
                imageUrl=getattr(p, "profile_image", None),
                category=p.role.lower()
            ))

        # --- LAYER 2: LISTINGS SEARCH (ServiceListing) ---
        # Note: We search 'ServiceListing' now instead of 'ServiceRequest'
        listing_stmt = (
            select(ServiceListing)
            .where(
                or_(
                    ServiceListing.title.ilike(search_pattern),
                    ServiceListing.service_type.ilike(search_pattern),
                    ServiceListing.location_city.ilike(search_pattern)
                )
            )
            .limit(limit)
        )

        listing_res = await db.execute(listing_stmt)
        listings = listing_res.scalars().all()

        for l in listings:
            results.append(serviceschema.SearchItemOut(
                id=str(l.id),
                title=l.title,
                subtitle=f"{l.service_type.replace('-', ' ').title()} - {l.status}",
                type="listing",
                imageUrl=None,
                category=l.service_type
            ))

        log.info(f"🔍 Search success for '{q}': {len(results)} items found.")
        return results

    except Exception as e:
        log.error(f"❌ Search Router Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The search engine is currently synchronizing. Please try again."
        )