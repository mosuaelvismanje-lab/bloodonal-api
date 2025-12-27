from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status

from app.dependencies import get_db
from app.domain.usecases import ConsultationUseCase
from app.domain.consultation_models import (
    RequestResponse,
    UserRoles,
    ChannelType,
)
from app.models.doctor import Doctor


class ConsultationService:
    """
    Application-level service that:
      1) Ensures the doctor exists
      2) Delegates to ConsultationUseCase (quota + payment logic)
      3) Translates domain errors into HTTP exceptions
    """

    def __init__(
        self,
        uc: ConsultationUseCase = Depends(),
        db: AsyncSession = Depends(get_db),
    ):
        self.uc = uc
        self.db = db

    async def request_consultation(
        self,
        user_id: str,
        doctor_id: str,
        caller_phone: str,
        channel: ChannelType = ChannelType.VOICE,
    ) -> RequestResponse:
        # 1) Verify doctor exists
        doctor = await self.db.get(Doctor, doctor_id)
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor '{doctor_id}' not found",
            )

        # 2) Delegate to domain use case
        try:
            return await self.uc.handle(
                caller_id=user_id,
                recipient_id=doctor_id,
                caller_phone=caller_phone,
                channel=channel,
                recipient_role=UserRoles.DOCTOR,
            )

        except ConsultationUseCase.FreeQuotaExceeded as exc:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=str(exc),
            )

        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process consultation",
            ) from exc
