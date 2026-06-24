from __future__ import annotations

import logging
from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.blood.domain.matching_service import MatchingService
from app.modules.blood.donors.repository import DonorRepository
from app.modules.blood.requests.repository import BloodRequestRepository
from app.modules.blood.requests.schemas import (
    BloodRequestCreate,
    BloodRequestResponse,
)
from app.modules.blood.requests.service import (
    BloodRequestConflictError,
    BloodRequestDependencyError,
    BloodRequestNotFoundError,
    BloodRequestProcessingError,
    BloodRequestService,
)
from app.modules.notification.channels.gateway import NotificationGatewayImpl

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blood-requests", tags=["Blood Requests"])


# =========================================================
# REQUEST MODELS
# =========================================================
class AcceptRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    donor_id: UUID = Field(...)


class BloodRequestMatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    request_id: str
    total_matches: int
    top_matches: List[Dict[str, Any]]


# =========================================================
# DEPENDENCIES
# =========================================================
def get_blood_request_repository() -> BloodRequestRepository:
    return BloodRequestRepository()


def get_donor_repository() -> DonorRepository:
    return DonorRepository()


def get_matching_service() -> MatchingService:
    return MatchingService()


def get_notification_gateway() -> NotificationGatewayImpl:
    return NotificationGatewayImpl()


def get_service(
    repo: BloodRequestRepository = Depends(get_blood_request_repository),
    donor_repo: DonorRepository = Depends(get_donor_repository),
    matching_service: MatchingService = Depends(get_matching_service),
    notifier: NotificationGatewayImpl = Depends(get_notification_gateway),
) -> BloodRequestService:
    return BloodRequestService(
        repo=repo,
        donor_repo=donor_repo,
        matching_service=matching_service,
        notifier=notifier,
    )


# =========================================================
# ERROR HANDLING
# =========================================================
def _raise_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, BloodRequestNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))

    if isinstance(exc, BloodRequestConflictError):
        return HTTPException(status_code=409, detail=str(exc))

    if isinstance(exc, BloodRequestProcessingError):
        return HTTPException(status_code=500, detail=str(exc))

    if isinstance(exc, BloodRequestDependencyError):
        return HTTPException(status_code=500, detail=str(exc))

    logger.exception("blood_request_unhandled_exception")
    return HTTPException(status_code=500, detail="Internal server error")


# =========================================================
# CREATE REQUEST
# =========================================================
@router.post(
    "/",
    response_model=BloodRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_request(
    data: BloodRequestCreate,
    emergency: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        result = await service.create_request(
            db=db,
            data=data,
            emergency=emergency,
        )

        await db.commit()
        await db.refresh(result)

        logger.info(
            "blood_request_created",
            extra={
                "request_id": str(getattr(result, "id", "")),
                "emergency": emergency,
            },
        )

        return result

    except Exception as exc:
        await db.rollback()
        raise _raise_http_error(exc)


# =========================================================
# GET ALL REQUESTS
# =========================================================
@router.get("/", response_model=List[BloodRequestResponse])
async def get_all_requests(
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        return await service.get_requests(db)
    except Exception as exc:
        raise _raise_http_error(exc)


# =========================================================
# FILTER BY CITY
# =========================================================
@router.get("/city/{city}", response_model=List[BloodRequestResponse])
async def get_by_city(
    city: str = Path(..., min_length=2, max_length=80),
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        return await service.get_city_requests(db, city.lower().strip())
    except Exception as exc:
        logger.exception("get_by_city_failed", extra={"city": city})
        raise _raise_http_error(exc)


# =========================================================
# MATCH REQUEST
# =========================================================
@router.get("/match/{request_id}", response_model=BloodRequestMatchResponse)
async def match_blood_request(
    request_id: UUID = Path(...),
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
    matcher: MatchingService = Depends(get_matching_service),
):
    try:
        request = await service.get_request_by_id(db, str(request_id))
        if request is None:
            raise BloodRequestNotFoundError(f"Request {request_id} not found")

        matches = await matcher.get_matches(
            db=db,
            blood_request=request,
            limit=limit,
        )

        if matches is None:
            matches = []

        return BloodRequestMatchResponse(
            request_id=str(request_id),
            total_matches=len(matches),
            top_matches=matches[:limit],
        )

    except Exception as exc:
        logger.exception(
            "matching_failed",
            extra={"request_id": str(request_id)},
        )
        raise _raise_http_error(exc)


# =========================================================
# ACCEPT REQUEST
# =========================================================
@router.post(
    "/accept/{request_id}",
    response_model=BloodRequestResponse,
)
async def accept_request(
    request_id: UUID = Path(...),
    payload: AcceptRequestBody = ...,
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        result = await service.accept_request(
            db=db,
            request_id=str(request_id),
            donor_id=str(payload.donor_id),
        )

        await db.commit()
        await db.refresh(result)

        logger.info(
            "request_accepted",
            extra={
                "request_id": str(request_id),
                "donor_id": str(payload.donor_id),
            },
        )

        return result

    except Exception as exc:
        await db.rollback()
        logger.exception(
            "accept_failed",
            extra={
                "request_id": str(request_id),
                "donor_id": str(payload.donor_id),
            },
        )
        raise _raise_http_error(exc)


# =========================================================
# COMPLETE REQUEST
# =========================================================
@router.post(
    "/complete/{request_id}",
    response_model=BloodRequestResponse,
)
async def complete_request(
    request_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        result = await service.complete_request(
            db=db,
            request_id=str(request_id),
        )

        await db.commit()
        await db.refresh(result)

        logger.info(
            "request_completed",
            extra={"request_id": str(request_id)},
        )

        return result

    except Exception as exc:
        await db.rollback()
        logger.exception(
            "complete_failed",
            extra={"request_id": str(request_id)},
        )
        raise _raise_http_error(exc)


# =========================================================
# CANCEL REQUEST
# =========================================================
@router.post(
    "/cancel/{request_id}",
    response_model=BloodRequestResponse,
)
async def cancel_request(
    request_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        result = await service.cancel_request(
            db=db,
            request_id=str(request_id),
        )

        await db.commit()
        await db.refresh(result)

        logger.info(
            "request_cancelled",
            extra={"request_id": str(request_id)},
        )

        return result

    except Exception as exc:
        await db.rollback()
        logger.exception(
            "cancel_failed",
            extra={"request_id": str(request_id)},
        )
        raise _raise_http_error(exc)


# =========================================================
# GET SINGLE REQUEST
# NOTE: keep this LAST so it does not shadow static routes
# =========================================================
@router.get("/{request_id}", response_model=BloodRequestResponse)
async def get_request_by_id(
    request_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    service: BloodRequestService = Depends(get_service),
):
    try:
        result = await service.get_request_by_id(db, str(request_id))
        if result is None:
            raise BloodRequestNotFoundError(f"Request {request_id} not found")
        return result
    except Exception as exc:
        raise _raise_http_error(exc)