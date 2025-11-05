# app/routers/doctors.py
import asyncio
import inspect
import logging
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.database import get_async_session
from app.services.doctor_service import DoctorService
from app.services.consultation_service import ConsultationService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/healthcare/doctors",
    tags=["healthcare", "doctors"],
)


async def _maybe_await(func: Any, *args, **kwargs):
    """
    If func is async, await it. If it's sync, run it in a thread.
    This allows gradual migration of service layer to async.
    """
    if inspect.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return await asyncio.to_thread(func, *args, **kwargs)


@router.get(
    "/online",
    response_model=List[schemas.DoctorDto],
    summary="List all online doctors",
)
async def list_online_doctors(
    db: AsyncSession = Depends(get_async_session),
    svc: DoctorService = Depends(DoctorService),  # keep as depends if your DI needs it
):
    """
    Returns all doctors who are currently online.
    Service method can be sync or async; we handle both.
    """
    try:
        return await _maybe_await(svc.get_online_doctors, db)
    except Exception as exc:
        logger.exception("Failed to list online doctors")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to list online doctors",
        ) from exc


@router.post(
    "/{doctor_id}/request",
    response_model=schemas.RequestResponse,
    summary="Request a consultation with a doctor",
)
async def request_consultation(
    doctor_id: str,
    user_id: str,  # consider replacing with Depends(get_current_user_id) later
    db: AsyncSession = Depends(get_async_session),
    consult_svc: ConsultationService = Depends(ConsultationService),
):
    """
    Attempts to open a free or paid consultation with the given doctor.
    Enforces free‐quota limits, then falls back to payment.
    """
    try:
        response = await _maybe_await(
            consult_svc.handle_doctor_consultation,
            db=db,
            user_id=user_id,
            doctor_id=doctor_id,
        )
        return response

    except getattr(consult_svc, "NotFoundError", Exception) as e:
        # Domain-level NotFoundError
        logger.warning("Doctor not found: %s (user=%s)", doctor_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) or "Doctor not found",
        )

    except getattr(consult_svc, "QuotaExceededError", Exception) as e:
        # Free quota exceeded and payment failed
        logger.info("Quota exceeded for user=%s trying to request doctor=%s", user_id, doctor_id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e),
        )

    except Exception as e:
        logger.exception("Unable to process consultation request for user=%s doctor=%s", user_id, doctor_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process consultation request",
        ) from e
