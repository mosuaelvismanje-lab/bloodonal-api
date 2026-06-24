from __future__ import annotations

import inspect
import logging
from importlib import import_module
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..repository import DonorRepository

logger = logging.getLogger(__name__)


# =========================================================
# FALLBACK REPOSITORIES
# =========================================================
class _NullDonorRepository:
    async def get_by_id(
        self,
        db: AsyncSession,
        donor_id: str,
        for_update: bool = False,
    ) -> None:
        return None


class _NullRequestRepository:
    async def count_active_matches(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> int:
        return 0

    async def count_accepted(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> int:
        return 0

    async def count_completed(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> int:
        return 0

    async def count_cancelled(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> int:
        return 0


class _NullRewardRepository:
    async def get_reward_profile(
        self,
        db: AsyncSession,
        donor_id: Any,
    ) -> None:
        return None


# =========================================================
# DASHBOARD SERVICE
# =========================================================
class DonorDashboardService:
    """
    Enterprise-grade donor dashboard aggregator.

    Responsibilities:
    - Read donor profile
    - Read request activity metrics
    - Read reward/referral profile
    - Return DTO-ready raw dict
    """

    REQUIRED_DONOR_METHODS = {"get_by_id"}
    REQUIRED_REQUEST_METHODS = {
        "count_active_matches",
        "count_accepted",
        "count_completed",
        "count_cancelled",
    }
    REQUIRED_REWARD_METHODS = {"get_reward_profile"}

    def __init__(
        self,
        donor_repo: Optional[Any] = None,
        request_repo: Optional[Any] = None,
        reward_repo: Optional[Any] = None,
    ) -> None:
        self.donor_repo = donor_repo or self._load_donor_repo()
        self.request_repo = request_repo or self._load_request_repo()
        self.reward_repo = reward_repo or self._load_reward_repo()

        self._validate_repo(
            self.donor_repo,
            self.REQUIRED_DONOR_METHODS,
            "DonorRepository",
        )
        self._validate_repo(
            self.request_repo,
            self.REQUIRED_REQUEST_METHODS,
            "RequestRepository",
        )
        self._validate_repo(
            self.reward_repo,
            self.REQUIRED_REWARD_METHODS,
            "RewardRepository",
        )

    # =========================================================
    # MAIN AGGREGATION
    # =========================================================
    async def get_dashboard(
        self,
        db: AsyncSession,
        donor_id: str,
    ) -> Optional[Dict[str, Any]]:
        donor_id = self._require_text(donor_id, "donor_id")

        donor = await self._maybe_await(
            self.donor_repo.get_by_id(db, donor_id)
        )

        if not donor:
            logger.warning(
                "donor_dashboard_not_found",
                extra={"donor_id": donor_id},
            )
            return None

        try:
            active_matches = await self._safe_count(
                self.request_repo.count_active_matches(db, donor_id),
                donor_id,
                "count_active_matches",
            )
            accepted = await self._safe_count(
                self.request_repo.count_accepted(db, donor_id),
                donor_id,
                "count_accepted",
            )
            completed = await self._safe_count(
                self.request_repo.count_completed(db, donor_id),
                donor_id,
                "count_completed",
            )
            cancelled = await self._safe_count(
                self.request_repo.count_cancelled(db, donor_id),
                donor_id,
                "count_cancelled",
            )

            reward_profile = await self._safe_reward_profile(
                db=db,
                donor_id=donor_id,
                donor_obj=donor,
            )

            success_rate = self._calculate_success_rate(
                completed,
                accepted,
            )

            wallet_id = getattr(donor, "wallet_id", None)
            if wallet_id is not None:
                wallet_id = str(wallet_id)
            elif reward_profile is not None and getattr(reward_profile, "wallet_id", None) is not None:
                wallet_id = str(reward_profile.wallet_id)
            else:
                wallet_id = None

            referral_code = getattr(donor, "referral_code", None)
            referral_count = int(getattr(donor, "referral_count", 0) or 0)
            donation_streak = int(getattr(donor, "donation_streak", 0) or 0)

            if reward_profile is not None:
                referral_code = getattr(reward_profile, "referral_code", referral_code)
                referral_count = int(getattr(reward_profile, "total_referrals", referral_count) or 0)
                donation_streak = int(getattr(reward_profile, "streak_count", donation_streak) or 0)

            points = int(
                (
                    getattr(reward_profile, "total_points", None)
                    if reward_profile is not None
                    and getattr(reward_profile, "total_points", None) is not None
                    else getattr(donor, "points", 0)
                )
                or 0
            )

            rank = (
                getattr(reward_profile, "current_rank", None)
                if reward_profile is not None
                and getattr(reward_profile, "current_rank", None)
                else getattr(donor, "rank_level", "Bronze")
            )

            dashboard = {
                # IDENTITY
                "donor_id": str(getattr(donor, "id")),
                "full_name": str(getattr(donor, "full_name", "")),
                "phone": str(getattr(donor, "phone", "")),
                "blood_group": str(getattr(donor, "blood_group", "")),
                "city": str(getattr(donor, "city", "")),

                # STATUS
                "is_available": bool(getattr(donor, "is_available", False)),
                "is_active": bool(getattr(donor, "is_active", True)),

                # REWARD / GAMIFICATION
                "points": points,
                "rank": str(rank),
                "wallet_id": wallet_id,
                "referral_code": referral_code,
                "referral_count": referral_count,
                "donation_streak": donation_streak,

                # ACTIVITY
                "active_matches": active_matches,
                "accepted_requests": accepted,
                "completed_donations": completed,
                "cancelled_requests": cancelled,

                # PERFORMANCE
                "success_rate": success_rate,
                "total_lives_helped": completed,
                "total_donations": completed,
                "successful_responses": accepted,
                "rejection_count": cancelled,

                # TIMELINE / STATUS
                "last_donation_date": getattr(donor, "last_donation_date", None),
                "next_eligible_date": getattr(donor, "next_eligible_date", None),
                "created_at": getattr(donor, "created_at", None),
                "updated_at": getattr(donor, "updated_at", None),

                # UI HELPERS
                "is_eligible": bool(getattr(donor, "is_available", False)),
            }

            logger.info(
                "donor_dashboard_loaded",
                extra={
                    "donor_id": donor_id,
                    "points": points,
                    "rank": rank,
                    "accepted": accepted,
                    "completed": completed,
                    "referrals": referral_count,
                    "streak": donation_streak,
                },
            )
            return dashboard

        except Exception as exc:
            logger.exception(
                "donor_dashboard_failed",
                extra={"donor_id": donor_id, "error": str(exc)},
            )
            return self._fallback_dashboard(donor)

    # =========================================================
    # SAFE WRAPPERS
    # =========================================================
    async def _safe_count(self, value: Any, donor_id: str, metric_name: str) -> int:
        try:
            result = await self._maybe_await(value)
            return int(result or 0)
        except Exception as exc:
            logger.warning(
                "dashboard_metric_unavailable",
                extra={
                    "donor_id": donor_id,
                    "metric": metric_name,
                    "error": str(exc),
                },
            )
            return 0

    async def _safe_reward_profile(
        self,
        db: AsyncSession,
        donor_id: str,
        donor_obj: Any,
    ) -> Any:
        try:
            return await self._maybe_await(
                self.reward_repo.get_reward_profile(
                    db,
                    getattr(donor_obj, "id", None),
                )
            )
        except Exception as exc:
            logger.warning(
                "reward_profile_unavailable",
                extra={
                    "donor_id": donor_id,
                    "error": str(exc),
                },
            )
            return None

    def _fallback_dashboard(self, donor: Any) -> Dict[str, Any]:
        """
        Donor-only fallback when request/reward modules fail.
        """
        points = int(getattr(donor, "points", 0) or 0)
        rank = str(getattr(donor, "rank_level", "Bronze"))
        completed = int(getattr(donor, "total_donations", 0) or 0)
        accepted = int(getattr(donor, "successful_responses", 0) or 0)
        cancelled = int(getattr(donor, "rejection_count", 0) or 0)
        active_matches = int(getattr(donor, "active_matches", 0) or 0)

        success_rate = self._calculate_success_rate(completed, accepted)

        return {
            "donor_id": str(getattr(donor, "id", "")),
            "full_name": str(getattr(donor, "full_name", "")),
            "phone": str(getattr(donor, "phone", "")),
            "blood_group": str(getattr(donor, "blood_group", "")),
            "city": str(getattr(donor, "city", "")),
            "is_available": bool(getattr(donor, "is_available", False)),
            "is_active": bool(getattr(donor, "is_active", True)),
            "points": points,
            "rank": rank,
            "wallet_id": None,
            "referral_code": getattr(donor, "referral_code", None),
            "referral_count": int(getattr(donor, "referral_count", 0) or 0),
            "donation_streak": int(getattr(donor, "donation_streak", 0) or 0),
            "active_matches": active_matches,
            "accepted_requests": accepted,
            "completed_donations": completed,
            "cancelled_requests": cancelled,
            "success_rate": success_rate,
            "total_lives_helped": completed,
            "total_donations": completed,
            "successful_responses": accepted,
            "rejection_count": cancelled,
            "last_donation_date": getattr(donor, "last_donation_date", None),
            "next_eligible_date": getattr(donor, "next_eligible_date", None),
            "created_at": getattr(donor, "created_at", None),
            "updated_at": getattr(donor, "updated_at", None),
            "is_eligible": bool(getattr(donor, "is_available", False)),
        }

    # =========================================================
    # FACTORY HELPERS
    # =========================================================
    def _load_donor_repo(self) -> Any:
        try:
            return DonorRepository()
        except Exception as exc:
            logger.warning("Falling back to null donor repository: %s", exc)
            return _NullDonorRepository()

    def _load_request_repo(self) -> Any:
        candidates = (
            "app.modules.blood.requests.repository.RequestRepository",
            "app.modules.blood.request.repository.RequestRepository",
            "app.modules.blood.donors.request_repository.RequestRepository",
            "app.modules.blood.donors.repository.RequestRepository",
        )

        for path in candidates:
            try:
                module_path, class_name = path.rsplit(".", 1)
                module = import_module(module_path)
                cls = getattr(module, class_name)
                return cls()
            except Exception:
                continue

        logger.warning(
            "No request repository found; dashboard activity metrics will default to zero."
        )
        return _NullRequestRepository()

    def _load_reward_repo(self) -> Any:
        candidates = (
            "app.modules.rewards.repository.RewardRepository",
        )

        for path in candidates:
            try:
                module_path, class_name = path.rsplit(".", 1)
                module = import_module(module_path)
                cls = getattr(module, class_name)
                return cls()
            except Exception:
                continue

        logger.warning(
            "No reward repository found; wallet/referral fields will be partial."
        )
        return _NullRewardRepository()

    # =========================================================
    # VALIDATION
    # =========================================================
    def _validate_repo(self, repo: Any, required_methods: set[str], name: str) -> None:
        missing = [method for method in required_methods if not hasattr(repo, method)]
        if missing:
            raise TypeError(f"{name} missing required methods: {missing}")

    def _require_text(self, value: Any, field: str) -> str:
        if value is None:
            raise ValueError(f"{field} is required")
        text = str(value).strip()
        if not text:
            raise ValueError(f"{field} cannot be empty")
        return text

    def _calculate_success_rate(self, completed: int, accepted: int) -> float:
        if accepted <= 0:
            return 0.0
        try:
            return round((completed / accepted) * 100, 2)
        except Exception:
            return 0.0

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value


# =========================================================
# FACTORY ENTRY POINT
# =========================================================
def create_dashboard_service(
    donor_repo: Optional[Any] = None,
    request_repo: Optional[Any] = None,
    reward_repo: Optional[Any] = None,
) -> DonorDashboardService:
    """
    Creates the dashboard aggregation service used by the API router.
    """
    return DonorDashboardService(
        donor_repo=donor_repo,
        request_repo=request_repo,
        reward_repo=reward_repo,
    )