import asyncio
import inspect
import logging
from typing import List, Callable, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.schemas.healthcare_providers import HealthcareProvider, HealthcareProviderCreate, HealthcareProviderUpdate
from app.crud.healthcare_provider import (
    create_provider,
    get_providers,
    get_provider_by_id,
    update_provider,
    delete_provider
)
from app.database import get_async_session
from config import settings
from app.models.healthcare_provider import ProviderType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["HealthcareProviders"])

SYNC_ENGINE = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=SYNC_ENGINE, expire_on_commit=False)


async def _run_sync_in_thread(fn: Callable, *args, **kwargs) -> Any:
    def _inner():
        with SyncSessionLocal() as db:
            return fn(db, *args, **kwargs)
    return await asyncio.to_thread(_inner)


async def _maybe_await_with_session(func: Callable, async_session: AsyncSession, *args, **kwargs):
    if inspect.iscoroutinefunction(func):
        return await func(async_session, *args, **kwargs)
    return await _run_sync_in_thread(func, *args, **kwargs)


#  CREATE
@router.post("/", response_model=HealthcareProvider, status_code=status.HTTP_201_CREATED)
async def create(p: HealthcareProviderCreate, db: AsyncSession = Depends(get_async_session)):
    if p.service_type and p.service_type not in ProviderType.__members__:
        raise HTTPException(status_code=400, detail="Invalid service_type")
    result = await _maybe_await_with_session(create_provider, db, p)
    return result


#  LIST WITH FILTERS
@router.get("/", response_model=List[HealthcareProvider])
async def list_all(
    skip: int = 0,
    limit: int = 100,
    service_type: Optional[str] = None,
    name: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session)
):
    providers = await _maybe_await_with_session(get_providers, db, skip, limit, service_type, name)
    return providers


#  GET ONE
@router.get("/{provider_id}", response_model=HealthcareProvider)
async def get_one(provider_id: int, db: AsyncSession = Depends(get_async_session)):
    provider = await _maybe_await_with_session(get_provider_by_id, db, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


#  UPDATE
@router.put("/{provider_id}", response_model=HealthcareProvider)
async def update(provider_id: int, data: HealthcareProviderUpdate, db: AsyncSession = Depends(get_async_session)):
    updated = await _maybe_await_with_session(update_provider, db, provider_id, data.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Provider not found")
    return updated


#  DELETE
@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(provider_id: int, db: AsyncSession = Depends(get_async_session)):
    deleted = await _maybe_await_with_session(delete_provider, db, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
    return None
