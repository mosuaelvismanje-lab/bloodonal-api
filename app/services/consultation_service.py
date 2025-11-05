from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, HTTPException, status

from app.dependencies import get_db
from app.domain.consultation import ConsultationUseCase
from app.domain.consultation_models import RequestResponse, UserRoles, ChannelType
from app.models.doctor import Doctor

class ConsultationService:
    """
    Application-level service that:
      1) Ensures the doctor exists
      2) Delegates to ConsultationUseCase (quota + payment logic)
      3) Translates domain errors into HTTPExceptions
    """

    def __init__(
        self,
        uc: ConsultationUseCase = Depends(),       # Dependency injection
        db: AsyncSession = Depends(get_db)          # Async session
    ):
        self.uc = uc
        self.db = db

    async def request_consultation(
        self,
        user_id: str,
        doctor_id: str,
        caller_phone: str   # Add phone number as a parameter
    ) -> RequestResponse:
        # 1) Verify doctor exists
        doctor = await self.db.get(Doctor, doctor_id)
        if doctor is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor {doctor_id!r} not found"
            )

        # 2) Handle consultation (free quota first, then payment)
        try:
            return await self.uc.handle(
                caller_id=user_id,
                recipient_id=doctor_id,
                caller_phone=caller_phone,
                channel=ChannelType.VOICE,      # Adjust channel if needed
                recipient_role=UserRoles.DOCTOR
            )
        except ConsultationUseCase.FreeQuotaExceeded as e:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process consultation: {str(e)}"
            )
