from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession  # Use the Async version
from sqlalchemy import select  # Async uses 'select' instead of 'query'

# Specific modular imports
from app.models import servicemodel
from app.schemas import serviceschema
from app.database import get_db  # Import from your existing app/database.py

router = APIRouter(prefix="/api/v1/services", tags=["Service Stack"])


@router.get("/search", response_model=list[serviceschema.SearchItemOut])
async def global_modular_search(
        q: str = Query(...),
        db: AsyncSession = Depends(get_db)  # Injecting your existing async session
):
    search_pattern = f"%{q}%"

    # In Async SQLAlchemy, we use db.execute(select(...))
    # 1. Search Users/Providers
    provider_stmt = select(servicemodel.ServiceUser).filter(
        servicemodel.ServiceUser.full_name.ilike(search_pattern)
    )
    result = await db.execute(provider_stmt)
    providers = result.scalars().all()

    # 2. Search Active Requests
    request_stmt = select(servicemodel.ServiceRequest).filter(
        servicemodel.ServiceRequest.title.ilike(search_pattern)
    )
    result = await db.execute(request_stmt)
    requests = result.scalars().all()

    # ... mapping logic remains the same ...
    results = []
    for p in providers:
        results.append(serviceschema.SearchItemOut(
            id=str(p.id),
            title=p.full_name,
            subtitle=p.role.capitalize(),
            type=p.role.lower(),
            imageUrl=p.profile_image,
            category=p.role
        ))

    # ... return results
    return results