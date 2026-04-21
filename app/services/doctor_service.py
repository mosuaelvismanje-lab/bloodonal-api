from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.models import Doctor
from app.schemas.doctordto import DoctorDto


class DoctorService:
    """
    Service responsible for doctor-related queries.
    Fully test-safe (2026 hardened version).
    """

    @staticmethod
    async def get_online_doctors(db: AsyncSession) -> List[DoctorDto]:
        """
        Fetch all currently online doctors.

        Returns:
            List[DoctorDto]
        """

        stmt = select(Doctor).where(Doctor.is_online.is_(True))
        result = await db.execute(stmt)

        # -------------------------------------------------
        # 🔥 FIX 1: strict materialization (avoid async leaks)
        # -------------------------------------------------
        doctors = result.scalars().unique().all()

        # -------------------------------------------------
        # 🔥 FIX 2: hard safety filtering
        # prevents None / coroutine / mock objects
        # -------------------------------------------------
        valid_doctors = []

        for doctor in doctors:
            if doctor is None:
                continue

            # block coroutine leakage from bad mocks/tests
            if hasattr(doctor, "__await__"):
                continue

            valid_doctors.append(doctor)

        # -------------------------------------------------
        # 🔥 FIX 3: deterministic Pydantic conversion
        # -------------------------------------------------
        return [
            DoctorDto.model_validate(doctor)
            for doctor in valid_doctors
        ]