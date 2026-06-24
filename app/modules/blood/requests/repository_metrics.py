from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.blood.requests.models import (
    BloodRequest,
    BloodRequestStatusEnum,
)


class BloodRequestMetricsRepository:
    """
    Enterprise-grade analytics repository.

    Responsibilities:
    - Dashboard metrics
    - Request analytics
    - Aggregation queries
    - Read-only statistics
    - No business logic
    """

    # =========================================================
    # TIME
    # =========================================================
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    # =========================================================
    # SAFE SCALAR
    # =========================================================
    def _scalar(self, db: Session, stmt) -> int:
        result = db.execute(stmt).scalar_one_or_none()
        return int(result or 0)

    # =========================================================
    # ACTIVE REQUESTS
    # =========================================================
    def count_active_requests(self, db: Session) -> int:
        stmt = (
            select(func.count(BloodRequest.id))
            .where(BloodRequest.is_deleted.is_(False))
            .where(BloodRequest.status == BloodRequestStatusEnum.ACTIVE)
            .where(BloodRequest.expires_at > self._now())
        )

        return self._scalar(db, stmt)

    # =========================================================
    # URGENT REQUESTS
    # =========================================================
    def count_urgent_requests(self, db: Session) -> int:
        stmt = (
            select(func.count(BloodRequest.id))
            .where(BloodRequest.is_deleted.is_(False))
            .where(BloodRequest.is_urgent.is_(True))
            .where(BloodRequest.status == BloodRequestStatusEnum.ACTIVE)
            .where(BloodRequest.expires_at > self._now())
        )

        return self._scalar(db, stmt)

    # =========================================================
    # COMPLETED REQUESTS
    # =========================================================
    def count_completed_requests(self, db: Session) -> int:
        stmt = (
            select(func.count(BloodRequest.id))
            .where(BloodRequest.is_deleted.is_(False))
            .where(BloodRequest.status == BloodRequestStatusEnum.COMPLETED)
        )

        return self._scalar(db, stmt)

    # =========================================================
    # CANCELLED REQUESTS
    # =========================================================
    def count_cancelled_requests(self, db: Session) -> int:
        stmt = (
            select(func.count(BloodRequest.id))
            .where(BloodRequest.is_deleted.is_(False))
            .where(BloodRequest.status == BloodRequestStatusEnum.CANCELLED)
        )

        return self._scalar(db, stmt)

    # =========================================================
    # TOTAL VIEWS
    # =========================================================
    def total_views(self, db: Session) -> int:
        stmt = (
            select(func.coalesce(func.sum(BloodRequest.total_views), 0))
            .where(BloodRequest.is_deleted.is_(False))
        )

        return self._scalar(db, stmt)

    # =========================================================
    # TOTAL ACTIVE OFFERS
    # =========================================================
    def total_active_offers(self, db: Session) -> int:
        stmt = (
            select(func.count(BloodRequest.id))
            .where(BloodRequest.is_deleted.is_(False))
            .where(BloodRequest.offer.is_not(None))
            .where(BloodRequest.status == BloodRequestStatusEnum.ACTIVE)
        )

        return self._scalar(db, stmt)

    # =========================================================
    # ACTIVE VIEWERS
    # =========================================================
    def active_viewers(self, db: Session) -> int:
        """
        Placeholder until realtime presence system exists.

        Later this should connect to:
        - websocket presence
        - redis
        - firebase presence
        - socket gateway
        """

        return 0

    # =========================================================
    # GLOBAL COMPATIBILITY %
    # =========================================================
    def compatibility_percent(self, db: Session) -> int:
        """
        Temporary approximation.

        Later:
        - compute from donor pool
        - blood group compatibility
        - geo radius
        - AI donor matching
        """

        active = self.count_active_requests(db)

        if active <= 0:
            return 0

        urgent = self.count_urgent_requests(db)

        percent = int(((active - urgent) / active) * 100)

        return max(0, min(percent, 100))

    # =========================================================
    # DASHBOARD SUMMARY
    # =========================================================
    def dashboard_summary(self, db: Session) -> Dict[str, Any]:
        return {
            "activeRequests": self.count_active_requests(db),
            "urgentRequests": self.count_urgent_requests(db),
            "completedRequests": self.count_completed_requests(db),
            "cancelledRequests": self.count_cancelled_requests(db),
            "totalViews": self.total_views(db),
            "activeOffers": self.total_active_offers(db),
            "liveViewerCount": self.active_viewers(db),
            "compatibleDonorRate": self.compatibility_percent(db),
        }

    # =========================================================
    # REQUEST DETAIL ANALYTICS
    # =========================================================
    def request_analytics(
        self,
        db: Session,
        request_id: str,
    ) -> Dict[str, Any]:

        stmt = (
            select(BloodRequest)
            .where(BloodRequest.id == request_id)
            .where(BloodRequest.is_deleted.is_(False))
        )

        request = db.execute(stmt).scalar_one_or_none()

        if not request:
            return {}

        return {
            "requestId": str(request.id),
            "views": int(request.total_views or 0),
            "activeOffers": 1 if request.offer else 0,
            "isUrgent": bool(request.is_urgent),
            "status": request.status,
            "compatibilityPercent": 0,
        }