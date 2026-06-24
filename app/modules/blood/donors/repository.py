from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Mapping, Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BloodDonor

logger = logging.getLogger(__name__)


class DonorRepository:
    """
    Enterprise-grade donor repository.

    Async version.

    Guarantees:
    - No commit (Unit of Work pattern)
    - Flush-only writes
    - Atomic counter updates
    - Deterministic query results
    - Strict field whitelist
    - Exact matching for router/adapter alignment
    - Consistent DB error visibility
    """

    ALLOWED_UPDATE_FIELDS = {
        "full_name",
        "phone",
        "city",
        "blood_group",
        "fcm_token",
        "is_available",
        "accepts_requests",
        "referral_code",
        "referred_by",
        "latitude",
        "longitude",
        "hospital_affiliation",
    }

    MAX_PAGE_SIZE = 100

    # =========================================================
    # INTERNAL HELPERS
    # =========================================================
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _require_str(self, value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")

        value = value.strip()
        if not value:
            raise ValueError(f"{field} cannot be empty")

        return value

    def _normalize_str(
        self,
        value: Any,
        field: str,
    ) -> Optional[str]:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string or None")

        value = value.strip()
        return value or None

    def _normalize_city(self, value: Any) -> Optional[str]:
        text = self._normalize_str(value, "city")
        return text.lower() if text else None

    def _normalize_blood_group(self, value: Any) -> Optional[str]:
        text = self._normalize_str(value, "blood_group")
        return text.upper() if text else None

    def _normalize_phone(self, value: Any) -> Optional[str]:
        return self._normalize_str(value, "phone")

    def _validate_limit_offset(
        self,
        limit: Optional[int],
        offset: int,
    ) -> None:
        if limit is not None and (
            not isinstance(limit, int) or limit <= 0
        ):
            raise ValueError("limit must be a positive integer")

        if not isinstance(offset, int) or offset < 0:
            raise ValueError("offset must be a non-negative integer")

    def _ensure_async_session(self, db: AsyncSession) -> None:
        if db is None:
            raise TypeError("db cannot be None")

        if not isinstance(db, AsyncSession):
            raise TypeError(
                "DonorRepository expects sqlalchemy.ext.asyncio.AsyncSession"
            )

    async def _execute(self, db: AsyncSession, stmt):
        self._ensure_async_session(db)

        try:
            return await db.execute(stmt)
        except SQLAlchemyError:
            logger.exception("database_execution_failed")
            raise

    async def _refresh(
        self,
        db: AsyncSession,
        donor: BloodDonor,
    ) -> BloodDonor:
        await db.refresh(donor)
        return donor

    def _calculate_success_rate(
        self,
        completed: int,
        accepted: int,
    ) -> float:
        if accepted <= 0:
            return 0.0

        return round((completed / accepted) * 100, 2)

    # =========================================================
    # WRITE OPERATIONS
    # =========================================================
    async def create(
        self,
        db: AsyncSession,
        donor: BloodDonor,
    ) -> BloodDonor:
        """
        Create donor without committing.
        """
        if not isinstance(donor, BloodDonor):
            raise TypeError("donor must be a BloodDonor instance")

        try:
            db.add(donor)
            await db.flush()
            return await self._refresh(db, donor)

        except SQLAlchemyError:
            logger.exception("create_donor_failed")
            raise

    async def update(
        self,
        db: AsyncSession,
        donor: BloodDonor,
        data: Mapping[str, Any],
    ) -> BloodDonor:
        """
        Safe field update with whitelist + normalization.
        """
        if not isinstance(donor, BloodDonor):
            raise TypeError("donor must be a BloodDonor instance")

        if not isinstance(data, Mapping):
            raise TypeError("data must be a mapping")

        try:
            for key, value in data.items():
                if key not in self.ALLOWED_UPDATE_FIELDS:
                    logger.warning(
                        "invalid_donor_update_field",
                        extra={
                            "field": key,
                            "donor_id": str(donor.id),
                        },
                    )
                    continue

                if key == "full_name":
                    setattr(
                        donor,
                        key,
                        self._normalize_str(value, "full_name"),
                    )

                elif key == "phone":
                    setattr(
                        donor,
                        key,
                        self._normalize_phone(value),
                    )

                elif key == "city":
                    setattr(
                        donor,
                        key,
                        self._normalize_city(value),
                    )

                elif key == "blood_group":
                    setattr(
                        donor,
                        key,
                        self._normalize_blood_group(value),
                    )

                elif key == "fcm_token":
                    setattr(
                        donor,
                        key,
                        self._normalize_str(
                            value,
                            "fcm_token",
                        ),
                    )

                elif key in {
                    "is_available",
                    "accepts_requests",
                }:
                    setattr(donor, key, bool(value))

                elif key in {
                    "referral_code",
                    "referred_by",
                    "hospital_affiliation",
                }:
                    setattr(
                        donor,
                        key,
                        self._normalize_str(value, key),
                    )

                else:
                    setattr(donor, key, value)

            donor.updated_at = self._now()

            await db.flush()
            return await self._refresh(db, donor)

        except SQLAlchemyError:
            logger.exception("update_donor_failed")
            raise

    async def update_availability(
        self,
        db: AsyncSession,
        donor: BloodDonor,
        is_available: bool,
    ) -> BloodDonor:
        if not isinstance(donor, BloodDonor):
            raise TypeError("donor must be a BloodDonor instance")

        try:
            donor.is_available = bool(is_available)
            donor.updated_at = self._now()

            await db.flush()
            return await self._refresh(db, donor)

        except SQLAlchemyError:
            logger.exception("update_availability_failed")
            raise

    async def update_last_donation(
        self,
        db: AsyncSession,
        donor: BloodDonor,
    ) -> BloodDonor:
        if not isinstance(donor, BloodDonor):
            raise TypeError("donor must be a BloodDonor instance")

        try:
            now = self._now()

            donor.last_donation_date = now

            # 56 DAYS ELIGIBILITY
            donor.next_eligible_date = now + timedelta(days=56)

            donor.total_donations = int(donor.total_donations or 0) + 1
            donor.completed_donations = int(donor.completed_donations or 0) + 1
            donor.total_lives_helped = int(donor.total_lives_helped or 0) + 1
            donor.donation_streak = int(donor.donation_streak or 0) + 1

            donor.is_available = False

            donor.success_rate = self._calculate_success_rate(
                donor.completed_donations,
                donor.accepted_requests,
            )

            donor.updated_at = now

            await db.flush()
            return await self._refresh(db, donor)

        except SQLAlchemyError:
            logger.exception("update_last_donation_failed")
            raise

    async def update_rank(
        self,
        db: AsyncSession,
        donor: BloodDonor,
        rank: str,
    ) -> BloodDonor:
        if not isinstance(donor, BloodDonor):
            raise TypeError("donor must be a BloodDonor instance")

        rank = self._require_str(rank, "rank")

        try:
            donor.rank_level = rank
            donor.updated_at = self._now()

            await db.flush()
            return await self._refresh(db, donor)

        except SQLAlchemyError:
            logger.exception("update_rank_failed")
            raise

    async def touch_last_seen(
        self,
        db: AsyncSession,
        donor: BloodDonor,
    ) -> BloodDonor:
        donor.last_seen_at = self._now()
        donor.updated_at = self._now()

        await db.flush()
        return await self._refresh(db, donor)

    # =========================================================
    # ATOMIC OPERATIONS
    # =========================================================
    async def add_points_atomic(
        self,
        db: AsyncSession,
        donor_id: str,
        points: int,
    ) -> Optional[BloodDonor]:
        donor_id = self._require_str(donor_id, "donor_id")

        if not isinstance(points, int) or points <= 0:
            raise ValueError("points must be a positive integer")

        stmt = (
            update(BloodDonor)
            .where(BloodDonor.id == donor_id)
            .values(
                points=func.coalesce(BloodDonor.points, 0) + points,
                successful_responses=func.coalesce(
                    BloodDonor.successful_responses,
                    0,
                ) + 1,
                updated_at=self._now(),
            )
            .execution_options(synchronize_session=False)
        )

        result = await self._execute(db, stmt)

        if not result.rowcount:
            return None

        return await self.get_by_id(db, donor_id)

    async def add_rejection_atomic(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Optional[BloodDonor]:
        donor_id = self._require_str(donor_id, "donor_id")

        stmt = (
            update(BloodDonor)
            .where(BloodDonor.id == donor_id)
            .values(
                rejection_count=func.coalesce(BloodDonor.rejection_count, 0) + 1,
                cancelled_requests=func.coalesce(BloodDonor.cancelled_requests, 0) + 1,
                updated_at=self._now(),
            )
            .execution_options(synchronize_session=False)
        )

        result = await self._execute(db, stmt)

        if not result.rowcount:
            return None

        return await self.get_by_id(db, donor_id)

    async def increment_active_matches(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Optional[BloodDonor]:
        donor_id = self._require_str(donor_id, "donor_id")

        stmt = (
            update(BloodDonor)
            .where(BloodDonor.id == donor_id)
            .values(
                active_matches=func.coalesce(BloodDonor.active_matches, 0) + 1,
                updated_at=self._now(),
            )
            .execution_options(synchronize_session=False)
        )

        result = await self._execute(db, stmt)

        if not result.rowcount:
            return None

        return await self.get_by_id(db, donor_id)

    async def increment_accepted_requests(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Optional[BloodDonor]:
        donor_id = self._require_str(donor_id, "donor_id")

        stmt = (
            update(BloodDonor)
            .where(BloodDonor.id == donor_id)
            .values(
                accepted_requests=func.coalesce(BloodDonor.accepted_requests, 0) + 1,
                updated_at=self._now(),
            )
            .execution_options(synchronize_session=False)
        )

        result = await self._execute(db, stmt)

        if not result.rowcount:
            return None

        donor = await self.get_by_id(db, donor_id)

        if donor:
            donor.success_rate = self._calculate_success_rate(
                donor.completed_donations,
                donor.accepted_requests,
            )
            await db.flush()

        return donor

    async def reset_availability(
        self,
        db: AsyncSession,
    ) -> int:
        stmt = (
            update(BloodDonor)
            .where(
                and_(
                    BloodDonor.is_active.is_(True),
                    or_(
                        BloodDonor.next_eligible_date.is_(None),
                        BloodDonor.next_eligible_date <= self._now(),
                    ),
                )
            )
            .values(
                is_available=True,
                updated_at=self._now(),
            )
        )

        result = await self._execute(db, stmt)
        return int(result.rowcount or 0)

    # =========================================================
    # READ OPERATIONS
    # =========================================================
    async def get_by_id(
        self,
        db: AsyncSession,
        donor_id: str,
        for_update: bool = False,
    ) -> Optional[BloodDonor]:
        donor_id = self._require_str(donor_id, "donor_id")

        stmt = select(BloodDonor).where(
            BloodDonor.id == donor_id
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self._execute(db, stmt)
        return result.scalars().one_or_none()

    async def get_by_phone(
        self,
        db: AsyncSession,
        phone: str,
    ) -> Optional[BloodDonor]:
        phone_norm = self._normalize_phone(phone)

        if not phone_norm:
            return None

        stmt = select(BloodDonor).where(
            BloodDonor.phone == phone_norm
        )

        result = await self._execute(db, stmt)
        return result.scalars().one_or_none()

    async def get_by_user_id(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> Optional[BloodDonor]:
        user_id = self._require_str(user_id, "user_id")

        stmt = select(BloodDonor).where(
            BloodDonor.user_id == user_id
        )

        result = await self._execute(db, stmt)
        return result.scalars().one_or_none()

    async def list_donors(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BloodDonor]:
        """
        Returns all donors ordered by newest first.
        """
        self._validate_limit_offset(limit, offset)

        stmt = (
            select(BloodDonor)
            .order_by(
                BloodDonor.created_at.desc(),
                BloodDonor.updated_at.desc(),
                BloodDonor.id.asc(),
            )
            .offset(offset)
            .limit(min(limit, self.MAX_PAGE_SIZE))
        )

        result = await self._execute(db, stmt)
        return result.scalars().all()

    async def get_active_donors(
        self,
        db: AsyncSession,
        city: Optional[str] = None,
        blood_group: Optional[str] = None,
        eligible_only: bool = True,
        limit: Optional[int] = None,
        offset: int = 0,
        for_update: bool = False,
    ) -> List[BloodDonor]:
        self._validate_limit_offset(limit, offset)

        stmt = select(BloodDonor).where(
            BloodDonor.is_active.is_(True)
        )

        if eligible_only:
            stmt = stmt.where(
                BloodDonor.is_available.is_(True),
                BloodDonor.accepts_requests.is_(True),
            )

        if city is not None:
            city_norm = self._normalize_city(city)
            if city_norm:
                stmt = stmt.where(
                    BloodDonor.city == city_norm
                )

        if blood_group is not None:
            blood_group_norm = self._normalize_blood_group(
                blood_group
            )
            if blood_group_norm:
                stmt = stmt.where(
                    BloodDonor.blood_group == blood_group_norm
                )

        stmt = stmt.order_by(
            BloodDonor.points.desc(),
            BloodDonor.success_rate.desc(),
            BloodDonor.updated_at.desc(),
            BloodDonor.id.asc(),
        )

        if for_update:
            stmt = stmt.with_for_update()

        if offset:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(
                min(limit, self.MAX_PAGE_SIZE)
            )

        result = await self._execute(db, stmt)
        return result.scalars().all()

    async def get_top_donors(
        self,
        db: AsyncSession,
        limit: int = 10,
        offset: int = 0,
    ) -> List[BloodDonor]:
        self._validate_limit_offset(limit, offset)

        stmt = (
            select(BloodDonor)
            .where(BloodDonor.is_active.is_(True))
            .order_by(
                func.coalesce(
                    BloodDonor.points,
                    0,
                ).desc(),
                func.coalesce(
                    BloodDonor.completed_donations,
                    0,
                ).desc(),
                func.coalesce(
                    BloodDonor.success_rate,
                    0,
                ).desc(),
                BloodDonor.updated_at.desc(),
                BloodDonor.id.asc(),
            )
            .offset(offset)
            .limit(
                min(limit, self.MAX_PAGE_SIZE)
            )
        )

        result = await self._execute(db, stmt)
        return result.scalars().all()

    # =========================================================
    # DASHBOARD
    # =========================================================
    def get_dashboard_stats(
        self,
        donor: BloodDonor,
    ) -> Dict[str, Any]:
        return {
            "donor_id": str(donor.id),
            "full_name": donor.full_name,
            "phone": donor.phone,
            "blood_group": donor.blood_group,
            "city": donor.city,
            "is_available": donor.is_available,
            "is_active": donor.is_active,
            "points": donor.points,
            "rank": donor.rank_level,
            "wallet_id": (
                str(donor.wallet_id)
                if donor.wallet_id
                else None
            ),
            "referral_code": donor.referral_code,
            "referral_count": donor.referral_count,
            "donation_streak": donor.donation_streak,
            "active_matches": donor.active_matches,
            "accepted_requests": donor.accepted_requests,
            "completed_donations": donor.completed_donations,
            "cancelled_requests": donor.cancelled_requests,
            "success_rate": donor.success_rate,
            "total_lives_helped": donor.total_lives_helped,
            "last_donation_date": (
                donor.last_donation_date.isoformat()
                if donor.last_donation_date
                else None
            ),
            "next_eligible_date": (
                donor.next_eligible_date.isoformat()
                if donor.next_eligible_date
                else None
            ),
        }