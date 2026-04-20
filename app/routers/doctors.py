import asyncio
import inspect
import logging
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

# ✅ ALIGNED DEPENDENCIES: Using project-wide auth and session logic
from app.api.dependencies import get_current_user, get_db_session
from app.repositories.usage_repo import SQLAlchemyUsageRepository

from app.domain.consultation_models import ChannelType, UserRoles
from app.schemas.doctordto import DoctorDto, RequestResponse
from app.services.doctor_service import DoctorService
from app.domain.usecases import ConsultationUseCase

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/healthcare/doctors",
    tags=["healthcare", "doctors"],
)


# -----------------------------
# Utility for async/sync services
# -----------------------------
async def _maybe_await(func: Any, *args, **kwargs):
    """
    If func is async, await it. If it's sync, run it in a thread.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


# -----------------------------
# List online doctors
# -----------------------------
@router.get(
    "/online",
    response_model=List[DoctorDto],
    summary="List all online doctors",
)
async def list_online_doctors(
        db: AsyncSession = Depends(get_db_session),
        svc: DoctorService = Depends(DoctorService),
        current_user=Depends(get_current_user),  # ✅ Protects list from public scrapers
):
    """
    Returns all doctors who are currently online.
    Requires a valid Firebase Token.
    """
    try:
        doctors = await _maybe_await(svc.get_online_doctors, db)
        return doctors
    except Exception as exc:
        logger.exception("Failed to list online doctors")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list online doctors",
        ) from exc


# -----------------------------
# Request a doctor consultation
# -----------------------------
@router.post(
    "/{doctor_id}/request",
    response_model=RequestResponse,
    summary="Request a consultation with a doctor",
)
async def request_consultation(
        doctor_id: str,
        caller_phone: str,
        db: AsyncSession = Depends(get_db_session),
        current_user=Depends(get_current_user),  # ✅ Identity taken from token
):
    """
    Attempts to open a free or paid consultation.
    Checks usage_counters table and handles payment status.
    """

    # ✅ STEP 1: Initialize the new Repository
    usage_repo = SQLAlchemyUsageRepository(db)

    # ✅ STEP 2: Provision UseCase with real dependencies
    consultation_uc = ConsultationUseCase(
        usage_repo=usage_repo,
        payment_gateway=None,  # Add real gateways as needed
        call_gateway=None,
        chat_gateway=None
    )

    try:
        channel = ChannelType.VOICE
        recipient_role = UserRoles.DOCTOR

        # ✅ STEP 3: Use current_user.uid to ensure the requester is the token owner
        response = await consultation_uc.handle(
            caller_id=current_user.uid,
            recipient_id=doctor_id,
            caller_phone=caller_phone,
            channel=channel,
            recipient_role=recipient_role,
        )

        # Explicitly commit the usage decrement/transaction
        await db.commit()
        return response

    except ConsultationUseCase.FreeQuotaExceeded as e:
        logger.info("Quota exceeded for user=%s", current_user.uid)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )

    except Exception as e:
        logger.exception(
            "Consultation failed for user=%s doctor=%s",
            current_user.uid,
            doctor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process consultation request",
        )