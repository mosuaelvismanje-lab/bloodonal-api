from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Doctor  # your SQLAlchemy model
from app.schemas.doctordto import DoctorDto


class DoctorService:
    async def get_online_doctors(self, db: AsyncSession) -> list[DoctorDto]:
        result = await db.execute(select(Doctor).where(Doctor.is_online == True))
        doctors = result.scalars().all()
        return [DoctorDto.from_orm(d) for d in doctors]
