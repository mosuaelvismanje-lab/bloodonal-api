import asyncio
import inspect
import logging
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.consultation_models import ChannelType, UserRoles
from app.schemas.doctordto import DoctorDto, RequestResponse
from app.database import get_async_session
from app.services.doctor_service import DoctorService
from app.domain.usecases import ConsultationUseCase

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/healthcare/doctors",
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
    db: AsyncSession = Depends(get_async_session),
    svc: DoctorService = Depends(DoctorService),
):
    """
    Returns all doctors who are currently online.
    Handles both async and sync service methods.
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
    user_id: str,
    caller_phone: str,
    db: AsyncSession = Depends(get_async_session),
    consultation_uc: ConsultationUseCase = Depends(lambda: ConsultationUseCase(
        usage_repo=None,  # replace with real repo if using DI container
        payment_gateway=None,
        call_gateway=None,
        chat_gateway=None
    )),
):
    """
    Attempts to open a free or paid consultation with the given doctor.
    Handles free quota limits and payment automatically.
    """
    try:
        # Use the VOICE channel as default for consultations
        channel = ChannelType.VOICE
        recipient_role = UserRoles.DOCTOR

        response = await _maybe_await(
            consultation_uc.handle,
            caller_id=user_id,
            recipient_id=doctor_id,
            caller_phone=caller_phone,
            channel=channel,
            recipient_role=recipient_role,
        )
        return response

    except ConsultationUseCase.FreeQuotaExceeded as e:
        logger.info("Quota exceeded for user=%s trying to request doctor=%s", user_id, doctor_id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )

    except Exception as e:
        logger.exception(
            "Unable to process consultation request for user=%s doctor=%s",
            user_id,
            doctor_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process consultation request",
        ) from e

