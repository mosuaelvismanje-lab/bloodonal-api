from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, desc, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dispatch.schemas import DispatchStatus

logger = logging.getLogger(__name__)

# =========================================================
# OPTIONAL MODELS (FAIL FAST IF MISSING)
# =========================================================
try:
    from app.models.service_request import ServiceRequest  # type: ignore
except Exception:
    ServiceRequest = None  # type: ignore

try:
    from app.models.donor import Donor  # type: ignore
except Exception:
    Donor = None  # type: ignore

try:
    from app.models.user import User  # type: ignore
except Exception:
    User = None  # type: ignore

# =========================================================
# BLOOD COMPATIBILITY (REPOSITORY LEVEL FILTER HELP)
# =========================================================
_BLOOD_COMPATIBILITY: dict[str, set[str]] = {
    "O-": {"O-"},
    "O+": {"O+", "O-"},
    "A-": {"A-", "O-"},
    "A+": {"A+", "A-", "O+", "O-"},
    "B-": {"B-", "O-"},
    "B+": {"B+", "B-", "O+", "O-"},
    "AB-": {"AB-", "A-", "B-", "O-"},
    "AB+": {"AB+", "AB-", "A+", "A-", "B+", "B-", "O+", "O-"},
}


class DispatchRepository:
    """
    DATA ACCESS LAYER ONLY

    Rules:
    - NO scoring
    - NO ranking
    - NO business logic
    - ONLY DB access + serialization + filtering helpers
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================
    # INTERNAL MODEL CHECKS
    # =========================================================
    def _require_service_request_model(self):
        if ServiceRequest is None:
            raise RuntimeError("ServiceRequest model not loaded")
        return ServiceRequest

    def _candidate_model(self):
        """
        Explicit candidate selection:
        - Donor first
        - User fallback
        - None if neither exists
        """
        if Donor is not None:
            return Donor
        if User is not None:
            return User
        return None

    # =========================================================
    # NEARBY REQUESTS
    # =========================================================
    async def fetch_nearby_requests(
        self,
        *,
        service_type: str,
        latitude: Optional[float],
        longitude: Optional[float],
        radius_km: float = 50.0,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """
        Fetch request rows from the DB and return safe dictionaries.

        Geo filtering is intentionally not done here anymore.
        Keep geospatial ranking/filtering in the service layer only.
        """
        model = self._require_service_request_model()

        service_type = (service_type or "").strip().lower()
        limit = max(int(limit or 200), 1)

        stmt = select(model)
        conditions = []

        # Service filter
        if hasattr(model, "service_type"):
            conditions.append(func.lower(model.service_type) == service_type)

        # Status filter
        if hasattr(model, "status"):
            conditions.append(
                or_(
                    func.upper(model.status) == "ACTIVE",
                    func.upper(model.status) == "OPEN",
                    func.upper(model.status) == "PENDING",
                    func.upper(model.status) == "URGENT",
                )
            )

        # Soft delete filter
        if hasattr(model, "deleted_at"):
            conditions.append(model.deleted_at.is_(None))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Ordering
        if hasattr(model, "created_at"):
            stmt = stmt.order_by(desc(model.created_at))
        elif hasattr(model, "updated_at"):
            stmt = stmt.order_by(desc(model.updated_at))

        stmt = stmt.limit(limit * 5)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        items: list[dict[str, Any]] = []

        for row in rows:
            payload = self._serialize_request(row)
            if not payload:
                continue

            # radius_km / latitude / longitude are kept for API compatibility
            # but geo distance calculation is owned by the service layer now.

            items.append(payload)

            if len(items) >= limit:
                break

        return items

    # =========================================================
    # REQUEST BY ID
    # =========================================================
    async def fetch_request_by_id(self, request_id: str) -> dict[str, Any] | None:
        model = self._require_service_request_model()

        request_id = str(request_id or "").strip()
        if not request_id:
            return None

        stmt = select(model)

        parsed_uuid = self._parse_uuid(request_id)

        if hasattr(model, "id"):
            if parsed_uuid is not None:
                stmt = stmt.where(model.id == parsed_uuid)
            else:
                stmt = stmt.where(model.id == request_id)
        else:
            return None

        if hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))

        result = await self.db.execute(stmt)
        row = result.scalar_one_or_none()

        return self._serialize_request(row) if row else None

    # =========================================================
    # CANDIDATE DONORS / PROVIDERS
    # =========================================================
    async def fetch_candidate_donors(
        self,
        *,
        service_type: str,
        blood_group: Optional[str],
        latitude: Optional[float],
        longitude: Optional[float],
        radius_km: float = 50.0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Fetch candidate donors/providers for assignment.

        Geo filtering is intentionally not done here anymore.
        Keep distance logic in the service layer only.
        """
        model = self._candidate_model()
        if model is None:
            raise RuntimeError("No donor or user model loaded")

        blood_group = self._normalize_blood(blood_group)
        limit = max(int(limit or 100), 1)

        stmt = select(model)
        conditions = []

        if hasattr(model, "is_active"):
            conditions.append(model.is_active.is_(True))

        if hasattr(model, "is_available"):
            conditions.append(model.is_available.is_(True))

        if hasattr(model, "deleted_at"):
            conditions.append(model.deleted_at.is_(None))

        # Explicit blood compatibility filter:
        # no func.upper(...).in_(...) pattern here
        if blood_group and hasattr(model, "blood_group"):
            allowed = _BLOOD_COMPATIBILITY.get(blood_group, set())
            if allowed:
                conditions.append(model.blood_group.in_(allowed))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        if hasattr(model, "created_at"):
            stmt = stmt.order_by(desc(model.created_at))
        elif hasattr(model, "updated_at"):
            stmt = stmt.order_by(desc(model.updated_at))
        elif hasattr(model, "id"):
            stmt = stmt.order_by(desc(model.id))

        stmt = stmt.limit(limit * 5)

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        items: list[dict[str, Any]] = []

        for row in rows:
            payload = self._serialize_candidate(row)
            if not payload:
                continue

            # radius_km / latitude / longitude are kept for API compatibility
            # but geo distance calculation is owned by the service layer now.
            payload["service_type"] = service_type

            items.append(payload)

            if len(items) >= limit:
                break

        return items

    # =========================================================
    # ASSIGNMENT PERSISTENCE
    # =========================================================
    async def assign_request_to_donor(
        self,
        *,
        request_id: str,
        donor_id: str,
    ) -> dict[str, Any]:
        model = self._require_service_request_model()

        request_id = str(request_id or "").strip()
        donor_id = str(donor_id or "").strip()

        if not request_id or not donor_id:
            return {
                "assigned": False,
                "reason": "request_id and donor_id are required",
            }

        request = await self._load_request(request_id)
        if request is None:
            return {
                "assigned": False,
                "reason": "Request not found",
            }

        now = datetime.now(timezone.utc)

        if hasattr(request, "assigned_donor_id"):
            request.assigned_donor_id = donor_id

        if hasattr(request, "assigned_provider_id"):
            request.assigned_provider_id = donor_id

        if hasattr(request, "status"):
            request.status = DispatchStatus.ASSIGNED.value

        if hasattr(request, "assigned_at"):
            request.assigned_at = now

        if hasattr(request, "updated_at"):
            request.updated_at = now

        try:
            await self.db.commit()
            await self.db.refresh(request)
        except Exception as exc:
            await self.db.rollback()
            logger.exception("Assignment failed: %s", exc)
            return {
                "assigned": False,
                "reason": "DB commit failed",
            }

        return {
            "assigned": True,
            "request_id": request_id,
            "donor_id": donor_id,
            "status": getattr(request, "status", DispatchStatus.ASSIGNED.value),
            "updated_at": now.isoformat(),
        }

    # =========================================================
    # SERIALIZATION
    # =========================================================
    def _serialize_request(self, row: Any) -> dict[str, Any]:
        if not row:
            return {}

        return {
            "id": self._read_value(row, "id"),
            "patient_name": self._read_value(row, "patient_name", "full_name", "fullName"),
            "blood_group": self._read_value(row, "blood_group", "bloodGroup"),
            "needed_units": self._int(self._read_value(row, "needed_units", "neededUnits")),
            "city": self._read_value(row, "city"),
            "latitude": self._float(self._read_value(row, "latitude"), allow_none=True),
            "longitude": self._float(self._read_value(row, "longitude"), allow_none=True),
            "is_urgent": self._bool(self._read_value(row, "is_urgent", "isUrgent")),
            "status": self._read_value(row, "status", default="ACTIVE"),
            "service_type": self._read_value(row, "service_type", "serviceType", default="blood"),
            "hospital_priority_level": self._int(
                self._read_value(row, "hospital_priority_level", "hospitalPriorityLevel")
            ),
            "created_at": self._read_datetime(row, "created_at", "createdAt"),
            "updated_at": self._read_datetime(row, "updated_at", "updatedAt"),
        }

    def _serialize_candidate(self, row: Any) -> dict[str, Any]:
        if not row:
            return {}

        return {
            "id": self._read_value(row, "id"),
            "full_name": self._read_value(row, "full_name", "fullName", "name"),
            "blood_group": self._read_value(row, "blood_group", "bloodGroup"),
            "city": self._read_value(row, "city"),
            "latitude": self._float(self._read_value(row, "latitude"), allow_none=True),
            "longitude": self._float(self._read_value(row, "longitude"), allow_none=True),
            "is_active": self._bool(self._read_value(row, "is_active", default=True)),
            "is_available": self._bool(self._read_value(row, "is_available", default=True)),
        }

    # =========================================================
    # HELPERS
    # =========================================================
    async def _load_request(self, request_id: str):
        model = self._require_service_request_model()

        parsed = self._parse_uuid(request_id)

        stmt = select(model)

        if hasattr(model, "id"):
            if parsed is not None:
                stmt = stmt.where(model.id == parsed)
            else:
                stmt = stmt.where(model.id == request_id)
        else:
            return None

        if hasattr(model, "deleted_at"):
            stmt = stmt.where(model.deleted_at.is_(None))

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    def _parse_uuid(self, value: str):
        try:
            return uuid.UUID(str(value))
        except Exception:
            return None

    def _normalize_blood(self, value: Any) -> Optional[str]:
        if not value:
            return None
        v = str(value).upper().strip()
        return v if v in _BLOOD_COMPATIBILITY else None

    def _read_value(
        self,
        obj: Any,
        *names: str,
        default: Any = None,
    ) -> Any:
        for name in names:
            if hasattr(obj, name):
                value = getattr(obj, name, None)
                if value is not None:
                    return value
        return default

    def _read_datetime(self, obj: Any, *names: str) -> Optional[datetime]:
        value = self._read_value(obj, *names, default=None)
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    def _safe_int(self, value: Any, fallback: int = 0) -> int:
        try:
            if value is None:
                return fallback
            if isinstance(value, bool):
                return int(value)
            return int(float(value))
        except Exception:
            return fallback

    def _int(self, v, default=0):
        try:
            return int(float(v))
        except Exception:
            return default

    def _float(self, v, default=0.0, allow_none=False):
        try:
            if v is None and allow_none:
                return None
            return float(v)
        except Exception:
            return default

    def _bool(self, v):
        return bool(v)