from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from sqlalchemy import select as sa_select, update as sa_update
from sqlalchemy.exc import MultipleResultsFound, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BloodRequest, BloodRequestStatusEnum

logger = logging.getLogger(__name__)


# =========================================================
# REPOSITORY EXCEPTIONS
# =========================================================
class BloodRequestRepositoryError(Exception):
    """Base repository error."""


class BloodRequestStateError(BloodRequestRepositoryError):
    """Invalid state transition."""


class BloodRequestQueryError(BloodRequestRepositoryError):
    """Invalid query or input."""


# =========================================================
# REPOSITORY
# =========================================================
class BloodRequestRepository:
    """
    Async repository for blood requests.

    Rules:
    - No commit
    - Flush-only writes
    - Strict input validation
    - Safe normalization
    - Deterministic queries
    """

    PATCH_ALLOWED_FIELDS: Set[str] = {
        "phone",
        "city",
        "hospital_location",
        "needed_units",
        "urgency_level",
        "is_urgent",        # legacy compatibility only
        "offer",
        "incentive_amount",
    }

    MAX_PAGE_SIZE = 100

    # =====================================================
    # INTERNAL HELPERS
    # =====================================================
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _require_identifier(self, value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise BloodRequestQueryError(f"{field} must be a string")
        value = value.strip()
        if not value:
            raise BloodRequestQueryError(f"{field} cannot be empty")
        return value

    def _normalize_text(self, value: Any, field: str) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise BloodRequestQueryError(f"{field} must be a string or None")
        value = value.strip()
        return value or None

    def _normalize_city(self, value: Any) -> Optional[str]:
        text = self._normalize_text(value, "city")
        return text.lower() if text else None

    def _normalize_blood_group(self, value: Any) -> Optional[str]:
        text = self._normalize_text(value, "blood_group")
        return text.upper() if text else None

    def _normalize_positive_int(self, value: Any, field: str) -> int:
        if not isinstance(value, int):
            raise BloodRequestQueryError(f"{field} must be an integer")
        if value <= 0:
            raise BloodRequestQueryError(f"{field} must be greater than zero")
        return value

    def _normalize_non_negative_int(self, value: Any, field: str) -> int:
        if not isinstance(value, int):
            raise BloodRequestQueryError(f"{field} must be an integer")
        if value < 0:
            raise BloodRequestQueryError(f"{field} cannot be negative")
        return value

    def _normalize_urgency_level(self, value: Any) -> int:
        level = self._normalize_positive_int(value, "urgency_level")
        if level < 1 or level > 4:
            raise BloodRequestQueryError("urgency_level must be between 1 and 4")
        return level

    def _normalize_bool(self, value: Any, field: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise BloodRequestQueryError(f"{field} must be a boolean")

    def _validate_pagination(
        self,
        limit: Optional[int],
        offset: int,
    ) -> Tuple[Optional[int], int]:
        if limit is not None:
            if not isinstance(limit, int):
                raise BloodRequestQueryError("limit must be integer")
            if limit <= 0:
                raise BloodRequestQueryError("limit must be > 0")

        if not isinstance(offset, int):
            raise BloodRequestQueryError("offset must be integer")
        if offset < 0:
            raise BloodRequestQueryError("offset cannot be negative")

        return limit, offset

    def _validate_timezone_aware(self, value: Any, field: str) -> datetime:
        if not isinstance(value, datetime):
            raise BloodRequestQueryError(f"{field} must be datetime")

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    def _assert_state(
        self,
        request: BloodRequest,
        expected: BloodRequestStatusEnum,
        action: str,
    ) -> None:
        if request.status != expected:
            raise BloodRequestStateError(
                f"{action}: expected {expected}, got {request.status}"
            )

    def _assert_not_deleted(self, request: BloodRequest, action: str) -> None:
        if request.is_deleted:
            raise BloodRequestStateError(f"{action}: request is deleted")

    def _ensure_async_session(self, db: AsyncSession) -> None:
        if db is None:
            raise TypeError("db cannot be None")
        if not isinstance(db, AsyncSession):
            raise TypeError(
                "BloodRequestRepository expects sqlalchemy.ext.asyncio.AsyncSession"
            )

    async def _refresh(self, db: AsyncSession, request: BloodRequest) -> BloodRequest:
        await db.refresh(request)
        return request

    def _base_active_stmt(self):
        now = self._now()
        return sa_select(BloodRequest).where(
            BloodRequest.is_deleted.is_(False),
            BloodRequest.status == BloodRequestStatusEnum.ACTIVE,
            BloodRequest.expires_at.is_not(None),
            BloodRequest.expires_at > now,
        )

    async def _execute(self, db: AsyncSession, stmt):
        self._ensure_async_session(db)
        try:
            return await db.execute(stmt)
        except SQLAlchemyError:
            logger.exception("database_execution_failed")
            raise

    # =====================================================
    # CREATE
    # =====================================================
    async def create(self, db: AsyncSession, request: BloodRequest) -> BloodRequest:
        if not isinstance(request, BloodRequest):
            raise TypeError("request must be BloodRequest")

        self._assert_not_deleted(request, "create")

        if request.expires_at is None:
            raise BloodRequestQueryError("expires_at is required")

        try:
            request.expires_at = self._validate_timezone_aware(
                request.expires_at,
                "expires_at",
            )

            request.urgency_level = self._normalize_urgency_level(
                getattr(request, "urgency_level", 1)
            )
            request.incentive_amount = self._normalize_non_negative_int(
                getattr(request, "incentive_amount", 0),
                "incentive_amount",
            )
            request.is_urgent = self._normalize_bool(
                getattr(request, "is_urgent", False),
                "is_urgent",
            )

            db.add(request)
            await db.flush()
            await self._refresh(db, request)

            logger.info(
                "blood_request_created",
                extra={"request_id": str(request.id)},
            )
            return request

        except SQLAlchemyError:
            logger.exception("create_failed")
            raise

    # =====================================================
    # READ
    # =====================================================
    async def get_active(
        self,
        db: AsyncSession,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        limit, offset = self._validate_pagination(limit, offset)

        stmt = self._base_active_stmt().order_by(
            BloodRequest.created_at.desc(),
            BloodRequest.id.asc(),
        ).offset(offset)

        if limit:
            stmt = stmt.limit(limit)

        result = await self._execute(db, stmt)
        return list(result.scalars().all())

    async def get_requests(
        self,
        db: AsyncSession,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        """
        Compatibility alias used by service/router.
        """
        return await self.get_active(db, limit=limit, offset=offset)

    async def get_by_city(
        self,
        db: AsyncSession,
        city: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        city = self._normalize_city(city)
        if not city:
            return []

        limit, offset = self._validate_pagination(limit, offset)

        stmt = self._base_active_stmt().where(
            BloodRequest.city == city
        ).offset(offset)

        if limit:
            stmt = stmt.limit(limit)

        result = await self._execute(db, stmt)
        return list(result.scalars().all())

    async def get_city_requests(
        self,
        db: AsyncSession,
        city: str,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        """
        Compatibility alias used by service/router.
        """
        return await self.get_by_city(db, city, limit=limit, offset=offset)

    async def get_by_id(
        self,
        db: AsyncSession,
        request_id: str,
        *,
        for_update: bool = False,
    ) -> Optional[BloodRequest]:
        request_id = self._require_identifier(request_id, "request_id")

        stmt = sa_select(BloodRequest).where(
            BloodRequest.id == request_id,
            BloodRequest.is_deleted.is_(False),
        )

        if for_update:
            stmt = stmt.with_for_update()

        try:
            result = await self._execute(db, stmt)
            return result.scalars().one_or_none()
        except MultipleResultsFound:
            logger.exception("duplicate_id_detected")
            raise

    async def get_request_by_id(
        self,
        db: AsyncSession,
        request_id: str,
        *,
        for_update: bool = False,
    ) -> Optional[BloodRequest]:
        """
        Compatibility alias used by service/router.
        """
        return await self.get_by_id(db, request_id, for_update=for_update)

    # =====================================================
    # ACCEPT
    # =====================================================
    async def accept_request(
        self,
        db: AsyncSession,
        request: BloodRequest,
        donor_id: str,
    ):
        donor_id = self._require_identifier(donor_id, "donor_id")

        self._assert_not_deleted(request, "accept")
        self._assert_state(request, BloodRequestStatusEnum.ACTIVE, "accept")

        if request.accepted_by:
            raise BloodRequestStateError("already accepted")

        request.status = BloodRequestStatusEnum.ACCEPTED
        request.accepted_by = donor_id
        request.accepted_at = self._now()

        await db.flush()
        await self._refresh(db, request)

        logger.info("request_accepted", extra={"request_id": str(request.id)})
        return request

    # =====================================================
    # COMPLETE
    # =====================================================
    async def complete_request(
        self,
        db: AsyncSession,
        request: BloodRequest,
    ):
        self._assert_not_deleted(request, "complete")
        self._assert_state(request, BloodRequestStatusEnum.ACCEPTED, "complete")

        request.status = BloodRequestStatusEnum.COMPLETED
        request.completed_at = self._now()

        await db.flush()
        await self._refresh(db, request)

        logger.info("request_completed", extra={"request_id": str(request.id)})
        return request

    # =====================================================
    # CANCEL
    # =====================================================
    async def cancel_request(
        self,
        db: AsyncSession,
        request: BloodRequest,
    ):
        self._assert_not_deleted(request, "cancel")

        if request.status == BloodRequestStatusEnum.COMPLETED:
            raise BloodRequestStateError("cannot cancel completed request")

        request.status = BloodRequestStatusEnum.CANCELLED

        await db.flush()
        await self._refresh(db, request)

        logger.info("request_cancelled", extra={"request_id": str(request.id)})
        return request

    # =====================================================
    # EXPIRE (BULK)
    # =====================================================
    async def expire_requests(self, db: AsyncSession) -> int:
        now = self._now()

        stmt = (
            sa_update(BloodRequest)
            .where(
                BloodRequest.is_deleted.is_(False),
                BloodRequest.status == BloodRequestStatusEnum.ACTIVE,
                BloodRequest.expires_at <= now,
            )
            .values(status=BloodRequestStatusEnum.EXPIRED)
            .execution_options(synchronize_session=False)
        )

        result = await self._execute(db, stmt)
        count = int(result.rowcount or 0)

        logger.info("expired_requests", extra={"count": count})
        return count

    # =====================================================
    # PATCH UPDATE
    # =====================================================
    async def update(
        self,
        db: AsyncSession,
        request: BloodRequest,
        data: Mapping[str, Any],
    ) -> BloodRequest:
        self._assert_not_deleted(request, "update")

        if not isinstance(data, Mapping):
            raise BloodRequestQueryError("data must be a mapping")

        unknown = set(data.keys()) - self.PATCH_ALLOWED_FIELDS
        if unknown:
            raise BloodRequestQueryError(f"invalid fields: {unknown}")

        try:
            for k, v in data.items():
                if k == "city":
                    setattr(request, k, self._normalize_city(v))
                elif k == "phone":
                    setattr(request, k, self._normalize_text(v, "phone"))
                elif k == "needed_units":
                    setattr(
                        request,
                        k,
                        self._normalize_positive_int(v, "needed_units"),
                    )
                elif k == "urgency_level":
                    setattr(request, k, self._normalize_urgency_level(v))
                    request.is_urgent = int(v) >= 3
                elif k == "is_urgent":
                    is_urgent = self._normalize_bool(v, "is_urgent")
                    setattr(request, k, is_urgent)
                    if is_urgent and int(getattr(request, "urgency_level", 1) or 1) < 3:
                        request.urgency_level = 3
                elif k == "incentive_amount":
                    setattr(
                        request,
                        k,
                        self._normalize_non_negative_int(v, "incentive_amount"),
                    )
                elif k == "offer":
                    setattr(request, k, self._normalize_text(v, "offer"))
                elif k == "hospital_location":
                    setattr(request, k, self._normalize_text(v, "hospital_location"))
                else:
                    setattr(request, k, v)

            await db.flush()
            await self._refresh(db, request)

            logger.info("request_updated", extra={"request_id": str(request.id)})
            return request

        except SQLAlchemyError:
            logger.exception("update_failed")
            raise

    # =====================================================
    # MATCH FILTERS
    # =====================================================
    async def get_active_by_filters(
        self,
        db: AsyncSession,
        city: Optional[str] = None,
        blood_group: Optional[str] = None,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[BloodRequest]:
        limit, offset = self._validate_pagination(limit, offset)

        stmt = self._base_active_stmt()

        if city:
            city = self._normalize_city(city)
            if city:
                stmt = stmt.where(BloodRequest.city == city)

        if blood_group:
            blood_group = self._normalize_blood_group(blood_group)
            if blood_group:
                stmt = stmt.where(BloodRequest.blood_group == blood_group)

        stmt = stmt.offset(offset)

        if limit:
            stmt = stmt.limit(limit)

        result = await self._execute(db, stmt)
        return list(result.scalars().all())