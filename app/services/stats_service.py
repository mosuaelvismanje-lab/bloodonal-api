from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession


from app.models.call_session import CallSession, CallStatus

from app.modules.payment.models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


class StatsService:
    """
    Enterprise Analytics Service

    Responsibilities:
    - Aggregate platform metrics
    - Provide clean DTO-like dict outputs
    - No formatting / presentation logic
    """

    # =========================================================
    # DASHBOARD METRICS
    # =========================================================
    @staticmethod
    async def get_dashboard_metrics(db: AsyncSession) -> Dict[str, Any]:
        """
        Returns platform-wide metrics for admin dashboard.

        Guarantees:
        - Safe aggregation
        - No crashes on NULL values
        - Structured logging
        """

        try:
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            # -------------------------
            # PAYMENT METRICS
            # -------------------------
            pending_stmt = select(func.count(Payment.id)).where(
                Payment.status == PaymentStatus.PENDING
            )

            revenue_stmt = select(func.sum(Payment.amount)).where(
                and_(
                    Payment.status == PaymentStatus.SUCCESS,
                    Payment.confirmed_at >= today_start,
                )
            )

            # -------------------------
            # CALL METRICS
            # -------------------------
            avg_duration_stmt = select(func.avg(CallSession.duration_seconds)).where(
                and_(
                    CallSession.status == CallStatus.COMPLETED,
                    CallSession.started_at >= today_start,
                )
            )

            call_volume_stmt = select(func.count(CallSession.id)).where(
                CallSession.started_at >= today_start
            )

            # -------------------------
            # EXECUTION
            # -------------------------
            res_pending = await db.execute(pending_stmt)
            res_revenue = await db.execute(revenue_stmt)
            res_duration = await db.execute(avg_duration_stmt)
            res_volume = await db.execute(call_volume_stmt)

            pending = int(res_pending.scalar() or 0)
            revenue = float(res_revenue.scalar() or 0.0)
            avg_duration = float(res_duration.scalar() or 0.0)
            volume = int(res_volume.scalar() or 0)

            metrics = {
                "total_awaiting_verification": pending,
                "total_revenue_today": round(revenue, 2),
                "avg_call_duration_seconds": round(avg_duration, 2),
                "total_calls_today": volume,
            }

            logger.info(
                "stats_dashboard_metrics_generated",
                extra={
                    "pending": pending,
                    "revenue": revenue,
                    "calls": volume,
                },
            )

            return metrics

        except Exception as exc:
            logger.exception(
                "stats_dashboard_metrics_failed",
                extra={"error": str(exc)},
            )
            raise

    # =========================================================
    # DOCTOR PERFORMANCE
    # =========================================================
    @staticmethod
    async def get_doctor_performance(
        db: AsyncSession,
        doctor_id: str
    ) -> Dict[str, Any]:
        """
        Returns performance KPIs for a doctor.

        Used for:
        - payouts
        - quality analytics
        """

        try:
            stmt = select(
                func.count(CallSession.id).label("total_calls"),
                func.sum(CallSession.duration_seconds).label("total_seconds"),
            ).where(
                and_(
                    CallSession.callee_id == doctor_id,
                    CallSession.status == CallStatus.COMPLETED,
                )
            )

            res = await db.execute(stmt)
            data = res.first()

            total_calls = int(data.total_calls or 0)
            total_seconds = int(data.total_seconds or 0)

            result = {
                "doctor_id": doctor_id,
                "total_calls": total_calls,
                "total_hours": round(total_seconds / 3600, 2),
            }

            logger.info(
                "stats_doctor_performance_generated",
                extra={
                    "doctor_id": doctor_id,
                    "calls": total_calls,
                },
            )

            return result

        except Exception as exc:
            logger.exception(
                "stats_doctor_performance_failed",
                extra={
                    "doctor_id": doctor_id,
                    "error": str(exc),
                },
            )
            raise