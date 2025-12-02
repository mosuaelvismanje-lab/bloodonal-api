import asyncio
import inspect
import logging
from typing import List, Callable, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.crud.healthcare_request import (
    create_healthcare_request,
    get_healthcare_requests,
    assign_provider,
)
from app.crud.healthcare_provider import get_provider_by_id
from app.database import get_async_session

from app.schemas.healthcare_requests import HealthcareRequest, HealthcareRequestCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/healthcare-requests", tags=["HealthcareRequests"])

# Lightweight sync session maker for legacy sync CRUD functions
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


@router.post("/", response_model=HealthcareRequest, status_code=status.HTTP_201_CREATED)
async def create(req: HealthcareRequestCreate, db: AsyncSession = Depends(get_async_session)):
    try:
        obj = await _maybe_await_with_session(create_healthcare_request, db, req)
        return obj
    except Exception as exc:
        logger.exception("Failed to create healthcare request")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create request"
        ) from exc


@router.get("/", response_model=List[HealthcareRequest])
async def list_all(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_async_session)):
    try:
        items = await _maybe_await_with_session(get_healthcare_requests, db, skip, limit)
        return items
    except Exception as exc:
        logger.exception("Failed to list healthcare requests")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not list requests"
        ) from exc


@router.put("/{request_id}/assign/{provider_id}", response_model=HealthcareRequest)
async def assign(request_id: int, provider_id: int, db: AsyncSession = Depends(get_async_session)):
    try:
        # Optional: check provider exists
        provider = await _maybe_await_with_session(get_provider_by_id, db, provider_id)
        if not provider:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")

        # Optional: validate service_type logic here
        # e.g., prevent assigning a lab to a nurse request
        # if provider.service_type not in allowed_types_for_request(request_id):
        #     raise HTTPException(status_code=400, detail="Invalid provider type for this request")

        obj = await _maybe_await_with_session(assign_provider, db, request_id, provider_id)
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        return obj
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to assign provider (request_id=%s provider_id=%s)", request_id, provider_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assignment failed"
        ) from exc
