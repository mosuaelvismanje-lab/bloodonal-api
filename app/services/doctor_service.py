from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Doctor
from app.schemas.doctordto import DoctorDto


class DoctorService:

    @staticmethod
    async def get_online_doctors(db: AsyncSession) -> list[DoctorDto]:
        stmt = select(Doctor).where(Doctor.is_online.is_(True))
        result = await db.execute(stmt)

        doctors = result.scalars().unique().all()

        return [
            DoctorDto.model_validate(doctor)
            for doctor in doctors
        ]
