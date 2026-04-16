import logging
from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ Standards-aligned Dependencies
from app.api.dependencies import get_db_session, get_current_user
from app.schemas.healthcare_providers import (
    HealthcareProvider,
    HealthcareProviderCreate,
    HealthcareProviderUpdate,
    HealthcareProviderShort
)
from app.crud.healthcare_provider import (
    create_provider,
    get_providers,
    get_provider_by_id,
    update_provider,
    delete_provider
)

logger = logging.getLogger(__name__)

# ✅ Versioning: Prefix set to /v1 to match production API layout
router = APIRouter(prefix="/v1/providers", tags=["HealthcareProviders"])


# -------------------------------------------------
# CREATE PROVIDER (Protected)
# -------------------------------------------------
@router.post("/", response_model=HealthcareProvider, status_code=status.HTTP_201_CREATED)
async def create(
        p: HealthcareProviderCreate,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)  # ✅ Secure: Admin/Staff only in production
):
    try:
        new_provider = await create_provider(db, p)
        await db.commit()  # ✅ Persistence: Required for AsyncSession
        await db.refresh(new_provider)
        return new_provider
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create provider: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating provider profile")


# -------------------------------------------------
# LIST/SEARCH PROVIDERS (Public or Protected)
# -------------------------------------------------
@router.get("/", response_model=List[Union[HealthcareProvider, HealthcareProviderShort]])
async def list_all(
        skip: int = 0,
        limit: int = 20,
        service_type: Optional[str] = None,
        name: Optional[str] = None,
        db: AsyncSession = Depends(get_db_session)
):
    """
    Search providers with autocomplete support.
    Example: /v1/providers/?name=General
    """
    try:
        # Search logic usually doesn't need explicit commits
        providers = await get_providers(db, skip, limit, service_type, name)
        return providers
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search service temporarily unavailable")


# -------------------------------------------------
# GET SINGLE PROVIDER
# -------------------------------------------------
@router.get("/{provider_id}", response_model=HealthcareProvider)
async def get_one(provider_id: int, db: AsyncSession = Depends(get_db_session)):
    provider = await get_provider_by_id(db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


# -------------------------------------------------
# UPDATE PROVIDER (Protected)
# -------------------------------------------------
@router.put("/{provider_id}", response_model=HealthcareProvider)
async def update(
        provider_id: int,
        data: HealthcareProviderUpdate,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    try:
        # Use exclude_unset=True so we don't overwrite existing data with Nulls
        updated = await update_provider(db, provider_id, data.model_dump(exclude_unset=True))
        if not updated:
            raise HTTPException(status_code=404, detail="Provider not found")

        await db.commit()
        return updated
    except Exception as e:
        await db.rollback()
        logger.error(f"Update failed for provider {provider_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update provider")


# -------------------------------------------------
# DELETE PROVIDER (Protected)
# -------------------------------------------------
@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
        provider_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user)
):
    try:
        deleted = await delete_provider(db, provider_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Provider not found")

        await db.commit()
        return None
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error during deletion")