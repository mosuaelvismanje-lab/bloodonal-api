from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DonorDashboardService:
    """
    Enterprise-grade Donor Dashboard Service.

    Rules:
    - Pure domain/service layer (no FastAPI)
    - Read-only orchestration
    - DTO-ready output
    - Repository contract validation
    - Async-safe, but tolerant of sync repositories
    """

    REQUIRED_DONOR_METHODS = {"get_by_id"}
    REQUIRED_REQUEST_METHODS = {
        "count_active_matches",
        "count_accepted",
        "count_completed",
        "count_cancelled",
    }

    def __init__(
        self,
        donor_repo,
        request_repo,
        reward_repo: Optional[Any] = None,
    ):
        if donor_repo is None or request_repo is None:
            raise ValueError("Missing required repositories")

        self._validate_repo(
            donor_repo,
            self.REQUIRED_DONOR_METHODS,
            "DonorRepository",
        )
        self._validate_repo(
            request_repo,
            self.REQUIRED_REQUEST_METHODS,
            "RequestRepository",
        )

        self.donor_repo = donor_repo
        self.request_repo = request_repo
        self.reward_repo = reward_repo

    # =========================================================
    # CONTRACT VALIDATION
    # =========================================================
    def _validate_repo(self, repo, required_methods: set[str], name: str):
        missing = [m for m in required_methods if not hasattr(repo, m)]
        if missing:
            raise TypeError(f"{name} missing required methods: {missing}")

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _to_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value if value is not None else default)
        except Exception:
            return default

    def _to_bool(self, value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = str(value).strip().lower()
        return text in {"true", "1", "yes", "y", "on"}

    def _calculate_success_rate(self, completed: int, accepted: int) -> float:
        if accepted <= 0:
            return 0.0
        try:
            return round((completed / accepted) * 100, 2)
        except Exception:
            return 0.0

    def _iso_or_none(self, value: Any):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                return None
        return value

    # =========================================================
    # MAIN DASHBOARD AGGREGATION
    # =========================================================
    async def get_dashboard(
        self,
        db,
        donor_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns raw dashboard data (DTO-ready).

        Returns None if donor not found or failure occurs.
        """
        if donor_id is None:
            return None

        donor_id = str(donor_id).strip()
        if not donor_id:
            return None

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
            active_matches = await self._safe_metric(
                self.request_repo.count_active_matches(db, donor_id),
                donor_id,
                "count_active_matches",
            )
            accepted = await self._safe_metric(
                self.request_repo.count_accepted(db, donor_id),
                donor_id,
                "count_accepted",
            )
            completed = await self._safe_metric(
                self.request_repo.count_completed(db, donor_id),
                donor_id,
                "count_completed",
            )
            cancelled = await self._safe_metric(
                self.request_repo.count_cancelled(db, donor_id),
                donor_id,
                "count_cancelled",
            )

            success_rate = self._calculate_success_rate(
                completed,
                accepted,
            )

            total_donations = self._to_int(
                getattr(donor, "total_donations", None),
                default=completed,
            )
            successful_responses = self._to_int(
                getattr(donor, "successful_responses", None),
                default=accepted,
            )
            rejection_count = self._to_int(
                getattr(donor, "rejection_count", None),
                default=cancelled,
            )

            wallet_id = getattr(donor, "wallet_id", None)
            if wallet_id is not None and hasattr(wallet_id, "hex"):
                wallet_id = str(wallet_id)
            elif wallet_id is not None:
                wallet_id = str(wallet_id)

            dashboard = {
                # IDENTITY
                "donor_id": str(getattr(donor, "id")),
                "full_name": getattr(donor, "full_name", ""),
                "phone": getattr(donor, "phone", ""),
                "blood_group": getattr(donor, "blood_group", ""),
                "city": getattr(donor, "city", ""),

                # STATUS
                "is_available": self._to_bool(
                    getattr(donor, "is_available", False),
                    default=False,
                ),
                "is_active": self._to_bool(
                    getattr(donor, "is_active", True),
                    default=True,
                ),

                # GAMIFICATION
                "points": self._to_int(getattr(donor, "points", 0)),
                "rank": getattr(donor, "rank_level", "Bronze"),
                "wallet_id": wallet_id,

                # REWARDS / REFERRALS
                "referral_code": getattr(donor, "referral_code", None),
                "referral_count": self._to_int(
                    getattr(donor, "referral_count", 0)
                ),
                "donation_streak": self._to_int(
                    getattr(donor, "donation_streak", 0)
                ),

                # ACTIVITY
                "active_matches": active_matches,
                "accepted_requests": accepted,
                "completed_donations": completed,
                "cancelled_requests": cancelled,

                # PERFORMANCE
                "success_rate": success_rate,
                "total_lives_helped": self._to_int(
                    getattr(donor, "total_lives_helped", completed),
                    default=completed,
                ),
                "total_donations": total_donations,
                "successful_responses": successful_responses,
                "rejection_count": rejection_count,

                # TIMELINE
                "last_donation_date": self._iso_or_none(
                    getattr(donor, "last_donation_date", None)
                ),
                "next_eligible_date": self._iso_or_none(
                    getattr(donor, "next_eligible_date", None)
                ),
                "created_at": self._iso_or_none(
                    getattr(donor, "created_at", None)
                ),
                "updated_at": self._iso_or_none(
                    getattr(donor, "updated_at", None)
                ),

                # UI HELPERS
                "is_eligible": self._to_bool(
                    getattr(donor, "is_available", False),
                    default=False,
                ),
            }

            logger.info(
                "donor_dashboard_loaded",
                extra={
                    "donor_id": donor_id,
                    "accepted": accepted,
                    "completed": completed,
                    "success_rate": success_rate,
                    "points": dashboard["points"],
                    "rank": dashboard["rank"],
                },
            )

            return dashboard

        except Exception as exc:
            logger.exception(
                "donor_dashboard_failed",
                extra={
                    "donor_id": donor_id,
                    "error": str(exc),
                },
            )
            return None

    async def _safe_metric(self, value: Any, donor_id: str, metric: str) -> int:
        try:
            result = await self._maybe_await(value)
            return self._to_int(result, default=0)
        except Exception as exc:
            logger.warning(
                "dashboard_metric_unavailable",
                extra={
                    "donor_id": donor_id,
                    "metric": metric,
                    "error": str(exc),
                },
            )
            return 0