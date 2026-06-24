from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.api.response import success

from .exceptions import (
    DonorDomainError,
    DonorNotFoundError,
    DuplicateDonorError,
    IneligibleDonorError,
)
from .schemas import (
    DonorCreate,
    DonorResponse,
    DonorUpdate,
)
from .service import DonorService
from .dtos import DonorDashboardDTO
from .seed.dashboard_factory import (
    DonorDashboardService,
    create_dashboard_service,
)
from ..services.reward_repository.donation_orchestrator import (
    DonationOrchestrator,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/donors",
    tags=["Donors"],
)


# =========================================================
# DEPENDENCIES
# =========================================================
def get_donor_service() -> DonorService:
    """
    Centralized donor service factory.
    """
    return DonorService()


def get_dashboard_service() -> DonorDashboardService:
    """
    Dashboard aggregation service factory.
    """
    return create_dashboard_service()


def get_orchestrator(
    service: DonorService = Depends(get_donor_service),
) -> DonationOrchestrator:
    """
    Donation orchestration dependency.
    """
    return DonationOrchestrator(
        donor_service=service,
    )


# =========================================================
# INTERNAL HELPERS
# =========================================================
def _normalize_city(city: Optional[str]) -> Optional[str]:
    if city is None:
        return None

    normalized = city.strip().lower()
    if not normalized:
        return None

    return normalized


def _normalize_blood_group(
    blood_group: Optional[str],
) -> Optional[str]:
    if blood_group is None:
        return None

    normalized = blood_group.strip().upper()
    if not normalized:
        return None

    return normalized


def _donor_response(donor: Any) -> Dict[str, Any]:
    """
    Serializes a SQLAlchemy donor object to a JSON-safe API payload.
    """
    return DonorResponse.model_validate(donor).model_dump(mode="json")


def _dashboard_response(dto: DonorDashboardDTO) -> Dict[str, Any]:
    """
    Explicit DTO serializer.
    """
    return {
        "donor_id": dto.donor_id,
        "full_name": dto.full_name,
        "phone": dto.phone,
        "blood_group": dto.blood_group,
        "city": dto.city,
        "is_available": dto.is_available,
        "is_active": dto.is_active,
        "points": dto.points,
        "rank": dto.rank,
        "wallet_id": dto.wallet_id,
        "referral_code": dto.referral_code,
        "referral_count": dto.referral_count,
        "donation_streak": dto.donation_streak,
        "active_matches": dto.active_matches,
        "accepted_requests": dto.accepted_requests,
        "completed_donations": dto.completed_donations,
        "cancelled_requests": dto.cancelled_requests,
        "success_rate": dto.success_rate,
        "total_lives_helped": dto.total_lives_helped,
        "total_donations": dto.total_donations,
        "successful_responses": dto.successful_responses,
        "rejection_count": dto.rejection_count,
        "last_donation_date": (
            dto.last_donation_date.isoformat()
            if dto.last_donation_date
            else None
        ),
        "next_eligible_date": (
            dto.next_eligible_date.isoformat()
            if dto.next_eligible_date
            else None
        ),
        "is_eligible": dto.is_eligible,
        "created_at": (
            dto.created_at.isoformat()
            if dto.created_at
            else None
        ),
        "updated_at": (
            dto.updated_at.isoformat()
            if dto.updated_at
            else None
        ),
    }


# =========================================================
# ERROR MAPPING
# =========================================================
def _map_exception(exc: Exception) -> HTTPException:
    if isinstance(exc, DonorNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(exc, DuplicateDonorError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )

    if isinstance(exc, IneligibleDonorError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        )

    if isinstance(exc, DonorDomainError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    logger.exception(
        "donor_unhandled_exception",
        extra={
            "exception_type": type(exc).__name__,
            "error": str(exc),
        },
    )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    )


# =========================================================
# CREATE DONOR
# =========================================================
@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
)
async def register_donor(
    data: DonorCreate,
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    try:
        donor = await service.register_donor(
            db=db,
            data=data,
        )

        await db.commit()
        await db.refresh(donor)

        logger.info(
            "donor_registered",
            extra={
                "donor_id": str(donor.id),
            },
        )

        return success(
            data=_donor_response(donor),
            message="Donor registered successfully",
        )

    except Exception as exc:
        await db.rollback()
        raise _map_exception(exc)


# =========================================================
# LIST ALL DONORS
# =========================================================
@router.get("/all")
async def list_all_donors(
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    """
    Returns all donors for admin/ops screens.
    """
    try:
        donors = await service.list_donors(
            db=db,
            limit=limit,
            offset=offset,
        )

        return success(
            data=[
                _donor_response(d)
                for d in donors
            ],
            message="Donors loaded successfully",
        )

    except Exception as exc:
        raise _map_exception(exc)


# =========================================================
# MATCHING DONORS
# =========================================================
@router.get("/")
async def get_matching_donors(
    city: Optional[str] = Query(
        default=None,
        max_length=100,
    ),
    blood_group: Optional[str] = Query(
        default=None,
        max_length=5,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    try:
        donors = await service.get_matching_donors(
            db=db,
            city=_normalize_city(city),
            blood_group=_normalize_blood_group(
                blood_group,
            ),
            limit=limit,
        )

        return success(
            data=[
                _donor_response(d)
                for d in donors
            ],
            message="Matching donors loaded successfully",
        )

    except Exception as exc:
        raise _map_exception(exc)


# =========================================================
# LEADERBOARD
# =========================================================
@router.get("/leaderboard/top")
async def get_leaderboard(
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    try:
        donors = await service.get_leaderboard(
            db=db,
            limit=limit,
        )

        return success(
            data=[
                _donor_response(d)
                for d in donors
            ],
            message="Leaderboard loaded successfully",
        )

    except Exception as exc:
        raise _map_exception(exc)


# =========================================================
# DONOR DASHBOARD
# =========================================================
@router.get("/{donor_id}/dashboard")
async def get_donor_dashboard(
    donor_id: UUID,
    db: AsyncSession = Depends(get_db),
    dashboard_service: DonorDashboardService = Depends(
        get_dashboard_service,
    ),
):
    """
    Full donor dashboard endpoint.

    Includes:
    - donor metrics
    - reward progress
    - referrals
    - streaks
    - donation analytics
    - eligibility state
    """
    try:
        raw_dashboard = await dashboard_service.get_dashboard(
            db=db,
            donor_id=str(donor_id),
        )

        if raw_dashboard is None:
            raise DonorNotFoundError(
                f"Donor not found: {donor_id}"
            )

        dto = DonorDashboardDTO.from_raw(
            raw_dashboard,
        )

        logger.info(
            "donor_dashboard_loaded",
            extra={
                "donor_id": str(donor_id),
                "points": dto.points,
                "rank": dto.rank,
                "referrals": dto.referral_count,
                "streak": dto.donation_streak,
                "donations": dto.total_donations,
            },
        )

        return success(
            data=_dashboard_response(dto),
            message="Dashboard loaded successfully",
        )

    except Exception as exc:
        raise _map_exception(exc)


# =========================================================
# GET DONOR
# =========================================================
@router.get("/{donor_id}")
async def get_donor(
    donor_id: UUID,
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    try:
        donor = await service.get_donor_by_id(
            db=db,
            donor_id=str(donor_id),
        )

        return success(
            data=_donor_response(donor),
            message="Donor loaded successfully",
        )

    except Exception as exc:
        raise _map_exception(exc)


# =========================================================
# UPDATE PROFILE
# =========================================================
@router.patch("/{donor_id}")
async def update_profile(
    donor_id: UUID,
    data: DonorUpdate,
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    try:
        donor = await service.update_profile(
            db=db,
            donor_id=str(donor_id),
            data=data,
        )

        await db.commit()
        await db.refresh(donor)

        logger.info(
            "donor_profile_updated",
            extra={
                "donor_id": str(donor.id),
            },
        )

        return success(
            data=_donor_response(donor),
            message="Profile updated",
        )

    except Exception as exc:
        await db.rollback()
        raise _map_exception(exc)


# =========================================================
# SET AVAILABILITY
# =========================================================
@router.patch("/{donor_id}/availability")
async def set_availability(
    donor_id: UUID,
    is_available: bool = Query(...),
    db: AsyncSession = Depends(get_db),
    service: DonorService = Depends(get_donor_service),
):
    try:
        donor = await service.set_availability(
            db=db,
            donor_id=str(donor_id),
            is_available=is_available,
        )

        await db.commit()
        await db.refresh(donor)

        logger.info(
            "donor_availability_updated",
            extra={
                "donor_id": str(donor.id),
                "is_available": donor.is_available,
            },
        )

        return success(
            data=_donor_response(donor),
            message="Availability updated",
        )

    except Exception as exc:
        await db.rollback()
        raise _map_exception(exc)


# =========================================================
# COMPLETE DONATION
# =========================================================
@router.post("/{donor_id}/mark-donation")
async def finalize_donation(
    donor_id: UUID,
    db: AsyncSession = Depends(get_db),
    orchestrator: DonationOrchestrator = Depends(
        get_orchestrator,
    ),
):
    """
    Finalize donor reward lifecycle.

    Includes:
    - donation completion
    - reward points
    - streak updates
    - referral rewards
    """
    try:
        donor = await orchestrator.complete_donation_flow(
            db=db,
            donor_id=str(donor_id),
        )

        await db.commit()
        await db.refresh(donor)

        logger.info(
            "donation_completed",
            extra={
                "donor_id": str(donor.id),
            },
        )

        return success(
            data=_donor_response(donor),
            message="Donation completed successfully",
        )

    except Exception as exc:
        await db.rollback()
        raise _map_exception(exc)