from __future__ import annotations

import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Protocol, runtime_checkable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blood.donors.repository import DonorRepository
from app.modules.blood.domain.enum import BloodRequestStatusEnum
from app.modules.blood.domain.matching_service import MatchingService
from app.modules.blood.requests.models import BloodRequest
from app.modules.blood.requests.repository import BloodRequestRepository

logger = logging.getLogger(__name__)


# =========================================================
# EXCEPTIONS
# =========================================================
class BloodRequestServiceError(Exception):
    pass


class BloodRequestDependencyError(BloodRequestServiceError):
    pass


class BloodRequestValidationError(BloodRequestServiceError):
    pass


class BloodRequestNotFoundError(BloodRequestServiceError):
    pass


class BloodRequestConflictError(BloodRequestServiceError):
    pass


class BloodRequestProcessingError(BloodRequestServiceError):
    pass


# =========================================================
# INPUT CONTRACT
# =========================================================
@runtime_checkable
class BloodRequestCreateLike(Protocol):
    patient_name: Any
    phone: Any
    city: Any
    blood_group: Any
    hospital_location: Any
    needed_units: Any
    urgency_level: Any
    is_urgent: Any
    offer: Any
    user_id: Any
    incentive_amount: Any


# =========================================================
# NOTIFIER CONTRACT
# =========================================================
@runtime_checkable
class NotificationGateway(Protocol):
    async def trigger_service_notifications(
        self,
        service_type: str,
        category: str,
        listing_id: str,
        user_id: Any,
    ) -> Any: ...

    async def send_push_to_topic(
        self,
        topic: str,
        title: str,
        body: str,
        data: Dict[str, Any],
    ) -> Any: ...

    async def send_call_signal(
        self,
        fcm_token: str,
        session_id: str,
        caller_name: str,
        call_mode: str,
        room_name: str,
    ) -> Any: ...


# =========================================================
# SERVICE
# =========================================================
class BloodRequestService:
    """
    Service layer = business rules + enrichment.

    Core DB fields stay in the model.
    UI/dashboard fields are computed here and attached before return.
    """

    REWARD_POINTS = 100
    TOP_LIMIT = 5

    ACTIVE = BloodRequestStatusEnum.ACTIVE
    ACCEPTED = BloodRequestStatusEnum.ACCEPTED
    COMPLETED = BloodRequestStatusEnum.COMPLETED
    CANCELLED = BloodRequestStatusEnum.CANCELLED

    RANKS = (
        ("Platinum", 1500),
        ("Gold", 800),
        ("Silver", 300),
        ("Bronze", 0),
    )

    NORMAL_EXPIRY_DAYS = 4
    URGENT_EXPIRY_DAYS = 2
    EMERGENCY_EXPIRY_HOURS = 24

    def __init__(
        self,
        repo: BloodRequestRepository,
        donor_repo: DonorRepository,
        matching_service: MatchingService,
        notifier: NotificationGateway,
    ) -> None:
        self.repo = repo
        self.donor_repo = donor_repo
        self.matching_service = matching_service
        self.notifier = notifier
        self._validate()

    # =====================================================
    # VALIDATION
    # =====================================================
    def _validate(self) -> None:
        if any(
            x is None
            for x in [self.repo, self.donor_repo, self.matching_service, self.notifier]
        ):
            raise BloodRequestDependencyError("Missing dependencies")

    # =====================================================
    # HELPERS
    # =====================================================
    def _require_text(self, value: Any, field: str) -> str:
        if value is None:
            raise BloodRequestValidationError(f"{field} required")
        v = str(value).strip()
        if not v:
            raise BloodRequestValidationError(f"{field} empty")
        return v

    def _require_int(self, value: Any, field: str) -> int:
        try:
            return int(value)
        except Exception as exc:
            raise BloodRequestValidationError(f"{field} must be int") from exc

    def _require_non_negative_int(self, value: Any, field: str) -> int:
        number = self._require_int(value, field)
        if number < 0:
            raise BloodRequestValidationError(f"{field} cannot be negative")
        return number

    def _require_float(self, value: Any, field: str) -> float:
        try:
            return float(value)
        except Exception as exc:
            raise BloodRequestValidationError(f"{field} must be float") from exc

    def _normalize_urgency_level(self, value: Any) -> int:
        level = self._require_int(value, "urgency_level")
        if level < 1 or level > 4:
            raise BloodRequestValidationError("urgency_level must be between 1 and 4")
        return level

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _auto_expiry(self, *, emergency: bool, urgency_level: int) -> datetime:
        now = self._now()

        if emergency:
            return now + timedelta(hours=self.EMERGENCY_EXPIRY_HOURS)

        if urgency_level >= 4:
            return now + timedelta(hours=self.EMERGENCY_EXPIRY_HOURS)

        if urgency_level >= 3:
            return now + timedelta(days=self.URGENT_EXPIRY_DAYS)

        return now + timedelta(days=self.NORMAL_EXPIRY_DAYS)

    def _derive_urgency_level(
        self,
        *,
        emergency: bool,
        is_urgent: bool,
        needed_units: int,
        incentive_amount: int = 0,
        explicit_level: Any = None,
    ) -> int:
        """
        1 = Normal
        2 = Moderate
        3 = High
        4 = Critical / Emergency
        """
        if explicit_level is not None:
            try:
                return self._normalize_urgency_level(explicit_level)
            except Exception:
                pass

        if emergency:
            return 4

        if needed_units >= 8:
            return 4

        if incentive_amount >= 50000:
            return 3

        if is_urgent:
            return 3

        if needed_units >= 5:
            return 3

        if needed_units >= 3:
            return 2

        return 1

    def _status_text(self, request: BloodRequest) -> str:
        status = getattr(request, "status", self.ACTIVE)
        return getattr(status, "value", str(status)).upper()

    def _is_expired(self, request: BloodRequest) -> bool:
        expires_at = getattr(request, "expires_at", None)
        if not expires_at:
            return False
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at <= self._now()

    def _compatible_percent(self, matches: List[Dict[str, Any]]) -> int:
        if not matches:
            return 0
        score = round(min(1.0, len(matches) / float(self.TOP_LIMIT)) * 100)
        return max(0, min(100, score))

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    def _top_match_score(self, matches: List[Dict[str, Any]]) -> int:
        best = 0
        for item in matches or []:
            try:
                score = int(item.get("score", 0) or 0)
            except Exception:
                score = 0
            if score > best:
                best = score
        return best

    def _attach_matches(
        self,
        request: BloodRequest,
        matches: List[Dict[str, Any]],
    ) -> None:
        total_matches = len(matches or [])
        setattr(request, "total_matches_found", total_matches)
        setattr(request, "top_match_score", self._top_match_score(matches))
        setattr(request, "active_offers", total_matches)
        setattr(request, "compatibility_percent", self._compatible_percent(matches))
        setattr(
            request,
            "total_matches_sent",
            int(getattr(request, "total_matches_sent", 0) or 0),
        )

    def _attach_ui_fields(
        self,
        request: BloodRequest,
        *,
        matches: List[Dict[str, Any]] | None = None,
    ) -> BloodRequest:
        """
        Attach computed fields expected by the frontend DTO/model.
        These are not persisted to the database.
        """
        matches = matches or []

        total_matches_found = len(matches)
        total_matches_sent = int(getattr(request, "total_matches_sent", 0) or 0)
        total_views = int(getattr(request, "total_views", 0) or 0)
        incentive_amount = int(getattr(request, "incentive_amount", 0) or 0)

        is_expired = self._is_expired(request)
        status = self._status_text(request)
        is_cancelled = status == "CANCELLED"

        existing_urgency = getattr(request, "urgency_level", None)
        urgency_level = 1
        try:
            if existing_urgency is not None:
                urgency_level = self._normalize_urgency_level(existing_urgency)
        except Exception:
            urgency_level = self._derive_urgency_level(
                emergency=bool(getattr(request, "is_urgent", False)),
                is_urgent=bool(getattr(request, "is_urgent", False)),
                needed_units=int(getattr(request, "needed_units", 1) or 1),
                incentive_amount=incentive_amount,
            )

        setattr(
            request,
            "distance_km",
            float(getattr(request, "distance_km", 0.0) or 0.0),
        )
        setattr(request, "urgency_level", urgency_level)
        setattr(request, "is_urgent", bool(getattr(request, "is_urgent", False)))
        setattr(request, "incentive_amount", incentive_amount)
        setattr(request, "active_offers", total_matches_found)
        setattr(request, "compatibility_percent", self._compatible_percent(matches))
        setattr(request, "is_expired", is_expired)
        setattr(request, "is_cancelled", is_cancelled)
        setattr(request, "total_matches_found", total_matches_found)
        setattr(
            request,
            "top_match_score",
            int(getattr(request, "top_match_score", 0) or 0),
        )
        setattr(request, "total_matches_sent", total_matches_sent)
        setattr(request, "total_views", total_views)
        setattr(
            request,
            "reward_points_awarded",
            int(getattr(request, "reward_points_awarded", 0) or 0),
        )
        setattr(request, "donor_rank_after", getattr(request, "donor_rank_after", None))
        setattr(request, "geo_distance_km", getattr(request, "geo_distance_km", None))
        setattr(
            request,
            "hospital_priority_score",
            getattr(request, "hospital_priority_score", None),
        )
        setattr(
            request,
            "emergency_override",
            bool(getattr(request, "emergency_override", False)),
        )

        return request

    async def _rank(self, db: AsyncSession, donor: Any) -> None:
        points = int(getattr(donor, "points", 0) or 0)
        for rank, threshold in self.RANKS:
            if points >= threshold:
                if getattr(donor, "rank_level", None) != rank:
                    await self._maybe_await(self.donor_repo.update_rank(db, donor, rank))
                return

    async def _get_request_or_fail(
        self,
        db: AsyncSession,
        request_id: str,
        *,
        for_update: bool = False,
    ) -> BloodRequest:
        request = await self._maybe_await(
            self.repo.get_request_by_id(db, request_id, for_update=for_update)
        )
        if not request:
            raise BloodRequestNotFoundError(f"Request not found: {request_id}")
        return request

    async def _get_donor_or_fail(
        self,
        db: AsyncSession,
        donor_id: str,
        *,
        for_update: bool = False,
    ) -> Any:
        donor = await self._maybe_await(
            self.donor_repo.get_by_id(db, donor_id, for_update=for_update)
        )
        if not donor:
            raise BloodRequestNotFoundError(f"Donor not found: {donor_id}")
        return donor

    def _assert_state(
        self,
        request: BloodRequest,
        expected: BloodRequestStatusEnum,
        action: str,
    ) -> None:
        if request.status != expected:
            raise BloodRequestProcessingError(
                f"{action}: expected {expected}, got {request.status}"
            )

    async def _safe_call(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        """
        Call a notifier method only if it exists.
        Await it if it returns a coroutine.
        """
        method = getattr(self.notifier, method_name, None)
        if method is None:
            logger.warning(
                "%s_missing_method",
                method_name,
                extra={"notifier": type(self.notifier).__name__},
            )
            return None

        result = method(*args, **kwargs)
        if inspect.isawaitable(result):
            return await result
        return result

    # =====================================================
    # CREATE
    # =====================================================
    async def create_request(
        self,
        db: AsyncSession,
        data: BloodRequestCreateLike,
        emergency: bool = False,
    ) -> BloodRequest:
        try:
            explicit_urgency = getattr(data, "urgency_level", None)
            needed_units = self._require_int(data.needed_units, "needed_units")
            incentive_amount = self._require_non_negative_int(
                getattr(data, "incentive_amount", 0),
                "incentive_amount",
            )

            is_urgent = bool(
                emergency
                or getattr(data, "is_urgent", False)
                or (explicit_urgency is not None and int(explicit_urgency) >= 3)
            )

            urgency_level = self._derive_urgency_level(
                emergency=bool(emergency),
                is_urgent=is_urgent,
                needed_units=needed_units,
                incentive_amount=incentive_amount,
                explicit_level=explicit_urgency,
            )

            expires_at = self._auto_expiry(
                emergency=bool(emergency),
                urgency_level=urgency_level,
            )

            request = BloodRequest(
                patient_name=self._require_text(data.patient_name, "patient_name"),
                phone=self._require_text(data.phone, "phone"),
                city=self._require_text(data.city, "city").lower(),
                blood_group=self._require_text(data.blood_group, "blood_group").upper(),
                hospital_location=self._require_text(
                    data.hospital_location,
                    "hospital_location",
                ),
                needed_units=needed_units,
                is_urgent=is_urgent,
                urgency_level=urgency_level,
                offer=self._require_text(data.offer, "offer"),
                user_id=data.user_id,
                incentive_amount=incentive_amount,
                expires_at=expires_at,
                status=self.ACTIVE,
            )

            saved = await self.repo.create(db, request)

            try:
                matches = await self._maybe_await(
                    self.matching_service.get_matches(
                        db=db,
                        blood_request=saved,
                        limit=self.TOP_LIMIT,
                    )
                )
            except Exception:
                logger.exception("matching_failed")
                matches = []

            matches = matches or []

            self._attach_matches(saved, matches)
            self._attach_ui_fields(saved, matches=matches)

            try:
                await self._broadcast(saved)
            except Exception:
                logger.exception("broadcast_failed")

            try:
                await self._notify_top(saved, matches)
            except Exception:
                logger.exception("notify_top_failed")

            return saved

        except IntegrityError as exc:
            raise BloodRequestConflictError("duplicate request") from exc
        except BloodRequestServiceError:
            raise
        except Exception as exc:
            logger.exception("create_request_failed")
            raise BloodRequestProcessingError() from exc

    # =====================================================
    # READ
    # =====================================================
    async def get_requests(
        self,
        db: AsyncSession,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        result = await self._maybe_await(
            self.repo.get_requests(db, limit=limit, offset=offset)
        )
        return list(result or [])

    async def get_request_by_id(
        self,
        db: AsyncSession,
        request_id: str,
        *,
        for_update: bool = False,
    ) -> BloodRequest:
        request = await self._get_request_or_fail(db, request_id, for_update=for_update)

        try:
            matches = await self._maybe_await(
                self.matching_service.get_matches(
                    db=db,
                    blood_request=request,
                    limit=self.TOP_LIMIT,
                )
            )
        except Exception:
            logger.exception("matching_failed")
            matches = []

        matches = matches or []

        self._attach_matches(request, matches)
        self._attach_ui_fields(request, matches=matches)
        return request

    async def get_city_requests(
        self,
        db: AsyncSession,
        city: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        result = await self._maybe_await(
            self.repo.get_city_requests(db, city, limit=limit, offset=offset)
        )
        return list(result or [])

    # =====================================================
    # ACCEPT
    # =====================================================
    async def accept_request(
        self,
        db: AsyncSession,
        request_id: str,
        donor_id: str,
    ) -> BloodRequest:
        request = await self._get_request_or_fail(db, request_id, for_update=True)

        if request.status != self.ACTIVE:
            raise BloodRequestConflictError("not active")

        await self._get_donor_or_fail(db, donor_id, for_update=True)

        updated = await self._maybe_await(
            self.repo.accept_request(db, request, donor_id)
        )

        await self._maybe_await(
            self.donor_repo.increment_accepted_requests(db, donor_id)
        )

        try:
            matches = await self._maybe_await(
                self.matching_service.get_matches(
                    db=db,
                    blood_request=updated,
                    limit=self.TOP_LIMIT,
                )
            )
        except Exception:
            logger.exception("matching_failed")
            matches = []

        matches = matches or []

        self._attach_matches(updated, matches)
        self._attach_ui_fields(updated, matches=matches)

        await self._safe_call(
            "send_push_to_topic",
            f"blood_request_{request.id}",
            "Accepted",
            "Request accepted",
            {"request_id": str(request.id), "donor_id": donor_id},
        )

        await self._broadcast(updated)
        return updated

    # =====================================================
    # COMPLETE
    # =====================================================
    async def complete_request(
        self,
        db: AsyncSession,
        request_id: str,
    ) -> BloodRequest:
        request = await self._get_request_or_fail(db, request_id, for_update=True)

        if request.status != self.ACCEPTED:
            raise BloodRequestConflictError("not accepted")

        donor_id = getattr(request, "accepted_by", None)
        if not donor_id:
            raise BloodRequestProcessingError("accepted_by missing")

        donor = await self._get_donor_or_fail(db, str(donor_id), for_update=True)

        updated = await self._maybe_await(self.repo.complete_request(db, request))

        await self._maybe_await(self.donor_repo.update_last_donation(db, donor))
        donor = (
            await self._maybe_await(
                self.donor_repo.add_points_atomic(db, str(donor.id), self.REWARD_POINTS)
            )
            or donor
        )
        await self._rank(db, donor)

        setattr(updated, "reward_points_awarded", self.REWARD_POINTS)
        setattr(updated, "donor_rank_after", getattr(donor, "rank_level", None))

        try:
            matches = await self._maybe_await(
                self.matching_service.get_matches(
                    db=db,
                    blood_request=updated,
                    limit=self.TOP_LIMIT,
                )
            )
        except Exception:
            logger.exception("matching_failed")
            matches = []

        matches = matches or []

        self._attach_matches(updated, matches)
        self._attach_ui_fields(updated, matches=matches)

        await self._safe_call(
            "send_push_to_topic",
            f"blood_request_{request.id}",
            "Completed",
            "Donation completed",
            {"request_id": str(request.id)},
        )

        return updated

    # =====================================================
    # CANCEL
    # =====================================================
    async def cancel_request(
        self,
        db: AsyncSession,
        request_id: str,
    ) -> BloodRequest:
        request = await self._get_request_or_fail(db, request_id, for_update=True)

        if request.status == self.COMPLETED:
            raise BloodRequestConflictError("already completed")

        updated = await self._maybe_await(self.repo.cancel_request(db, request))

        try:
            matches = await self._maybe_await(
                self.matching_service.get_matches(
                    db=db,
                    blood_request=updated,
                    limit=self.TOP_LIMIT,
                )
            )
        except Exception:
            logger.exception("matching_failed")
            matches = []

        matches = matches or []

        self._attach_matches(updated, matches)
        self._attach_ui_fields(updated, matches=matches)

        await self._safe_call(
            "send_push_to_topic",
            f"blood_request_{request.id}",
            "Cancelled",
            "Request cancelled",
            {"request_id": str(request.id)},
        )

        return updated

    # =====================================================
    # NOTIFICATIONS
    # =====================================================
    async def _broadcast(self, request: BloodRequest) -> None:
        await self._safe_call(
            "trigger_service_notifications",
            "BLOOD_REQUEST",
            "BLOOD",
            str(request.id),
            request.user_id,
        )

    async def _notify_top(
        self,
        request: BloodRequest,
        matches: List[Dict[str, Any]],
    ) -> None:
        for item in (matches or [])[: self.TOP_LIMIT]:
            donor = (item or {}).get("donor") or {}
            token = donor.get("fcm_token")
            if not token:
                continue

            try:
                await self._safe_call(
                    "send_call_signal",
                    fcm_token=token,
                    session_id=str(request.id),
                    caller_name="Alert",
                    call_mode="BLOOD",
                    room_name=f"blood_{request.city}",
                )
            except Exception:
                logger.exception("notify_failed")