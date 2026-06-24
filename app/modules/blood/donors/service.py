from __future__ import annotations

import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import (
    DonorDomainError,
    DonorNotFoundError,
    DuplicateDonorError,
    IneligibleDonorError,
)
from .models import BloodDonor
from .repository import DonorRepository
from .schemas import DonorCreate, DonorUpdate
from .services.availability_service import AvailabilityService
from ...notification import notification_service

logger = logging.getLogger(__name__)


class DonorService:
    """
    Enterprise-grade Donor Service.

    Async version.

    Guarantees:
    - Strict domain boundary enforcement
    - Idempotent-safe state transitions
    - Concurrency-aware updates
    - No silent mutation
    - Clear transaction ownership (external)
    - Dashboard-ready response formatting
    """

    MIN_DONATION_GAP_DAYS = 90

    RANKS = (
        ("Platinum", 1500),
        ("Gold", 800),
        ("Silver", 300),
        ("Bronze", 0),
    )

    def __init__(
        self,
        repo: Optional[DonorRepository] = None,
        availability: Optional[AvailabilityService] = None,
        notifier: Any = None,
    ) -> None:
        self.repo = repo or DonorRepository()
        self.availability = availability or AvailabilityService()
        self.notifier = notifier or notification_service

        if not hasattr(self.availability, "is_eligible"):
            raise RuntimeError(
                "AvailabilityService must implement is_eligible()"
            )

    # =========================================================
    # CREATE
    # =========================================================
    async def register_donor(
        self,
        db: AsyncSession,
        data: DonorCreate,
    ) -> BloodDonor:
        phone = self._require_text(data.phone, "phone")

        existing = await self.repo.get_by_phone(db, phone)
        if existing:
            raise DuplicateDonorError(phone)

        try:
            donor = self._build_donor(data)

            created = await self.repo.create(db, donor)

            logger.info(
                "donor_created",
                extra={"donor_id": str(created.id)},
            )

            return created

        except IntegrityError as exc:
            raise DuplicateDonorError(phone) from exc

    # =========================================================
    # READ SINGLE
    # =========================================================
    async def get_donor_by_id(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> BloodDonor:
        return await self._get_or_fail(db, donor_id)

    # =========================================================
    # LIST ALL DONORS
    # =========================================================
    async def list_donors(
        self,
        db: AsyncSession,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BloodDonor]:
        limit = self._require_positive_int(limit, "limit")
        offset = self._require_non_negative_int(offset, "offset")

        if not hasattr(self.repo, "list_donors"):
            raise RuntimeError(
                "DonorRepository must implement list_donors()"
            )

        return await self.repo.list_donors(
            db=db,
            limit=limit,
            offset=offset,
        )

    # =========================================================
    # MATCHING
    # =========================================================
    async def get_matching_donors(
        self,
        db: AsyncSession,
        city: Optional[str],
        blood_group: Optional[str],
        limit: int = 50,
    ) -> List[BloodDonor]:
        limit = self._require_positive_int(limit, "limit")

        return await self.repo.get_active_donors(
            db=db,
            city=city,
            blood_group=blood_group,
            eligible_only=True,
            limit=limit,
        )

    # =========================================================
    # LEADERBOARD
    # =========================================================
    async def get_leaderboard(
        self,
        db: AsyncSession,
        limit: int = 10,
    ) -> List[BloodDonor]:
        limit = self._require_positive_int(limit, "limit")

        return await self.repo.get_top_donors(
            db,
            limit=limit,
        )

    # =========================================================
    # UPDATE PROFILE
    # =========================================================
    async def update_profile(
        self,
        db: AsyncSession,
        donor_id: str,
        data: DonorUpdate,
    ) -> BloodDonor:
        donor = await self._get_or_fail(db, donor_id)

        payload = data.model_dump(
            exclude_unset=True,
            by_alias=False,
        )

        if not payload:
            return donor

        if "full_name" in payload and payload["full_name"] is not None:
            payload["full_name"] = self._require_text(
                payload["full_name"],
                "full_name",
            )

        if "phone" in payload and payload["phone"] is not None:
            payload["phone"] = self._require_text(
                payload["phone"],
                "phone",
            )

            existing = await self.repo.get_by_phone(
                db,
                payload["phone"],
            )
            if existing and str(existing.id) != str(donor.id):
                raise DuplicateDonorError(payload["phone"])

        if "city" in payload and payload["city"] is not None:
            payload["city"] = self._require_text(
                payload["city"],
                "city",
            ).lower()

        if "blood_group" in payload and payload["blood_group"] is not None:
            payload["blood_group"] = self._require_text(
                payload["blood_group"],
                "blood_group",
            ).upper()

        if "referral_code" in payload and payload["referral_code"] is not None:
            payload["referral_code"] = self._require_text(
                payload["referral_code"],
                "referral_code",
            )

        if "referred_by" in payload and payload["referred_by"] is not None:
            payload["referred_by"] = self._require_text(
                payload["referred_by"],
                "referred_by",
            )

        if "fcm_token" in payload and payload["fcm_token"] is not None:
            payload["fcm_token"] = self._require_text(
                payload["fcm_token"],
                "fcm_token",
            )

        updated = await self.repo.update(
            db,
            donor,
            payload,
        )

        logger.info(
            "donor_profile_updated",
            extra={"donor_id": donor_id},
        )

        return updated

    # =========================================================
    # AVAILABILITY
    # =========================================================
    async def set_availability(
        self,
        db: AsyncSession,
        donor_id: str,
        is_available: bool,
    ) -> BloodDonor:
        donor = await self._get_or_fail(db, donor_id)

        if (
            is_available
            and not self.availability.is_eligible(
                donor
            )
        ):
            raise IneligibleDonorError(
                f"Cooldown active. Next: "
                f"{self._next_eligible_date(donor)}"
            )

        updated = await self.repo.update_availability(
            db,
            donor,
            is_available,
        )

        logger.info(
            "donor_availability_changed",
            extra={
                "donor_id": donor_id,
                "is_available": is_available,
            },
        )

        return updated

    # =========================================================
    # DONATION FLOW
    # =========================================================
    async def mark_donation_complete(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> BloodDonor:
        donor = await self._get_or_fail(db, donor_id)

        if (
            donor.last_donation_date
            and self._is_recent(donor.last_donation_date)
        ):
            logger.warning(
                "duplicate_donation_attempt",
                extra={"donor_id": donor_id},
            )
            return donor

        donor = await self.repo.update_last_donation(
            db,
            donor,
        )

        donor = (
            await self.repo.add_points_atomic(
                db,
                str(donor.id),
                50,
            )
            or donor
        )

        await self._sync_rank(db, donor)

        donor.is_available = False

        await self._safe_notify(donor)

        logger.info(
            "donation_completed",
            extra={"donor_id": donor_id},
        )

        return donor

    async def complete_donation_flow(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> BloodDonor:
        return await self.mark_donation_complete(db, donor_id)

    # =========================================================
    # REWARDS
    # =========================================================
    async def add_reward_points(
        self,
        db: AsyncSession,
        donor_id: str,
        points: int,
    ) -> BloodDonor:
        donor_id = self._require_text(
            donor_id,
            "donor_id",
        )

        points = self._require_positive_int(
            points,
            "points",
        )

        donor = await self.repo.add_points_atomic(
            db,
            donor_id,
            points,
        )

        if not donor:
            raise DonorNotFoundError(donor_id)

        await self._sync_rank(db, donor)

        return donor

    async def record_rejection(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> BloodDonor:
        donor_id = self._require_text(
            donor_id,
            "donor_id",
        )

        donor = await self.repo.add_rejection_atomic(
            db,
            donor_id,
        )

        if not donor:
            raise DonorNotFoundError(donor_id)

        await self._sync_rank(db, donor)

        return donor

    # =========================================================
    # DASHBOARD
    # =========================================================
    async def get_dashboard(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Dict[str, Any]:
        donor = await self._get_or_fail(db, donor_id)

        points = int(donor.points or 0)
        total_donations = int(donor.total_donations or 0)
        successful_responses = int(
            donor.successful_responses or 0
        )
        rejection_count = int(
            donor.rejection_count or 0
        )

        total_attempts = (
            successful_responses + rejection_count
        )

        success_rate = (
            round(
                (successful_responses / total_attempts) * 100,
                2,
            )
            if total_attempts > 0
            else 0.0
        )

        return {
            "donor_id": str(donor.id),
            "full_name": donor.full_name,
            "phone": donor.phone,
            "blood_group": donor.blood_group,
            "city": donor.city,
            "is_available": donor.is_available,
            "is_active": donor.is_active,
            "points": points,
            "rank": donor.rank_level,
            "wallet_id": None,
            "referral_code": donor.referral_code,
            "referral_count": 0,
            "donation_streak": total_donations,
            "active_matches": successful_responses,
            "accepted_requests": successful_responses,
            "completed_donations": total_donations,
            "cancelled_requests": rejection_count,
            "success_rate": success_rate,
            "total_lives_helped": total_donations,
            "last_donation_date": donor.last_donation_date,
            "created_at": donor.created_at,
        }

    # =========================================================
    # SUMMARY / ANALYTICS
    # =========================================================
    async def get_donor_summary(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Dict[str, Any]:
        d = await self._get_or_fail(db, donor_id)

        eligible = self.availability.is_eligible(
            d
        )

        return {
            "profile": {
                "id": str(d.id),
                "full_name": d.full_name,
                "name": d.full_name,
                "blood_group": d.blood_group,
                "rank": d.rank_level,
                "is_available": d.is_available,
            },
            "stats": {
                "points": int(d.points or 0),
                "donations": int(d.total_donations or 0),
                "rejections": int(d.rejection_count or 0),
            },
            "medical": {
                "last_donation": d.last_donation_date,
                "next_eligible": self._next_eligible_date(d),
                "eligible": eligible,
                "is_eligible": eligible,
            },
        }

    async def get_donor_summary_legacy(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Dict[str, Any]:
        return await self.get_donor_summary(
            db,
            donor_id,
        )

    # =========================================================
    # RANK ENGINE
    # =========================================================
    async def _sync_rank(
        self,
        db: AsyncSession,
        donor: BloodDonor,
    ) -> None:
        points = int(
            getattr(donor, "points", 0) or 0
        )

        for rank, threshold in self.RANKS:
            if points >= threshold:
                if donor.rank_level != rank:
                    await self.repo.update_rank(
                        db,
                        donor,
                        rank,
                    )
                break

    # =========================================================
    # INTERNALS
    # =========================================================
    async def _get_or_fail(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> BloodDonor:
        donor_id = self._require_text(
            donor_id,
            "donor_id",
        )

        donor = await self.repo.get_by_id(
            db,
            donor_id,
        )

        if not donor:
            raise DonorNotFoundError(donor_id)

        return donor

    def _build_donor(
        self,
        data: DonorCreate,
    ) -> BloodDonor:
        return BloodDonor(
            full_name=self._require_text(
                data.full_name,
                "full_name",
            ),
            phone=self._require_text(
                data.phone,
                "phone",
            ),
            city=self._require_text(
                data.city,
                "city",
            ).lower(),
            blood_group=self._require_text(
                data.blood_group,
                "blood_group",
            ).upper(),
            is_available=bool(
                getattr(data, "is_available", True)
            ),
            is_active=True,
            fcm_token=getattr(
                data,
                "fcm_token",
                None,
            ),
            referral_code=getattr(
                data,
                "referral_code",
                None,
            ),
            referred_by=getattr(
                data,
                "referred_by",
                None,
            ),
            points=0,
            total_donations=0,
            successful_responses=0,
            rejection_count=0,
            rank_level="Bronze",
        )

    def _next_eligible_date(
        self,
        donor: BloodDonor,
    ) -> Optional[datetime]:
        if not donor.last_donation_date:
            return None

        return donor.last_donation_date + timedelta(
            days=self.MIN_DONATION_GAP_DAYS
        )

    def _is_recent(self, dt: datetime) -> bool:
        return (
            datetime.now(timezone.utc) - dt
        ).days < 1

    async def _safe_notify(
        self,
        donor: BloodDonor,
    ) -> None:
        try:
            if (
                donor.fcm_token
                and hasattr(
                    self.notifier,
                    "send_donation_thank_you",
                )
            ):
                result = self.notifier.send_donation_thank_you(
                    donor
                )

                if inspect.isawaitable(result):
                    await result

        except Exception:
            logger.exception(
                "notification_failed",
                extra={"donor_id": str(donor.id)},
            )

    def _require_text(
        self,
        value: Any,
        field: str,
    ) -> str:
        if value is None:
            raise DonorDomainError(
                f"{field} is required"
            )

        text_value = str(value).strip()

        if not text_value:
            raise DonorDomainError(
                f"{field} cannot be empty"
            )

        return text_value

    def _require_positive_int(
        self,
        value: Any,
        field: str,
    ) -> int:
        try:
            number = int(value)
        except Exception as exc:
            raise DonorDomainError(
                f"{field} must be an integer"
            ) from exc

        if number <= 0:
            raise DonorDomainError(
                f"{field} must be greater than zero"
            )

        return number

    def _require_non_negative_int(
        self,
        value: Any,
        field: str,
    ) -> int:
        try:
            number = int(value)
        except Exception as exc:
            raise DonorDomainError(
                f"{field} must be an integer"
            ) from exc

        if number < 0:
            raise DonorDomainError(
                f"{field} must be greater than or equal to zero"
            )

        return number