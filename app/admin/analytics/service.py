from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blood.domain.ai.repository import AIRepository
from app.modules.blood.wallet.models import WalletTransaction
from app.modules.hospital.subscriptions.models import HospitalSubscription
from app.modules.payment.models import Payment, PaymentStatus

logger = logging.getLogger(__name__)


# =========================================================
# SERVICE
# =========================================================
class AnalyticsService:
    """
    Enterprise-grade analytics engine.

    Guarantees:
    - No business mutation (read-only)
    - Safe aggregation queries
    - Centralized time window handling
    - Consistent numeric normalization
    - AI insights integration
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_repo = AIRepository(db)

    # =========================================================
    # TIME UTIL
    # =========================================================
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _range(self, days: int) -> tuple[datetime, datetime]:
        end = self._now()
        start = end - timedelta(days=days)
        return start, end

    # =========================================================
    # REVENUE METRICS
    # =========================================================
    async def get_revenue_metrics(self, days: int = 1) -> Dict[str, Any]:
        start, end = self._range(days)

        stmt = select(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
        ).where(
            Payment.status == PaymentStatus.SUCCESS,
            Payment.created_at >= start,
            Payment.created_at <= end,
        )

        revenue, tx_count = (await self.db.execute(stmt)).one()

        revenue = float(revenue or 0)
        tx_count = int(tx_count or 0)

        avg = revenue / tx_count if tx_count > 0 else 0.0

        return {
            "total_revenue": revenue,
            "total_transactions": tx_count,
            "average_transaction": avg,
            "period_days": days,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

    # =========================================================
    # PAYMENT BREAKDOWN
    # =========================================================
    async def get_payment_status_breakdown(self) -> Dict[str, int]:
        stmt = select(
            Payment.status,
            func.count(Payment.id),
        ).group_by(Payment.status)

        result = await self.db.execute(stmt)

        breakdown: Dict[str, int] = {
            "SUCCESS": 0,
            "PENDING": 0,
            "FAILED": 0,
            "AWAITING_VERIFICATION": 0,
        }

        for status, count in result.all():
            key = status.value if hasattr(status, "value") else str(status)
            breakdown[key] = int(count or 0)

        return breakdown

    # =========================================================
    # WALLET FLOW
    # =========================================================
    async def get_wallet_flow(self) -> Dict[str, Any]:
        stmt = select(
            func.coalesce(
                func.sum(
                    case((WalletTransaction.amount > 0, WalletTransaction.amount), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((WalletTransaction.amount < 0, WalletTransaction.amount), else_=0)
                ),
                0,
            ),
        )

        inflow, outflow = (await self.db.execute(stmt)).one()

        inflow = float(inflow or 0)
        outflow = float(outflow or 0)

        return {
            "total_inflow": inflow,
            "total_outflow": outflow,
            "net_flow": inflow + outflow,
        }

    # =========================================================
    # DONOR ACTIVITY
    # =========================================================
    async def get_donor_activity(self, user_id: Optional[UUID] = None) -> Dict[str, Any]:
        if user_id:
            stats = await self.ai_repo.get_donor_stats(user_id)
            success_rate = await self.ai_repo.get_success_rate(user_id)
            avg_response = await self.ai_repo.get_average_response_time(user_id)

            return {
                "user_id": str(user_id),
                "stats": stats,
                "success_rate": success_rate,
                "avg_response_minutes": avg_response,
            }

        stmt = select(
            func.count(WalletTransaction.id),
            func.coalesce(func.sum(WalletTransaction.amount), 0),
        ).where(
            WalletTransaction.type == "REWARD",
            WalletTransaction.status == "SUCCESS",
        )

        rewards, points = (await self.db.execute(stmt)).one()

        return {
            "total_rewards": int(rewards or 0),
            "total_points_distributed": float(points or 0),
        }

    # =========================================================
    # SUBSCRIPTION METRICS
    # =========================================================
    async def get_subscription_metrics(self) -> Dict[str, Any]:
        now = self._now()

        total_stmt = select(func.count(HospitalSubscription.id))

        active_stmt = select(func.count(HospitalSubscription.id)).where(
            HospitalSubscription.status == "ACTIVE",
            HospitalSubscription.end_date > now,
        )

        expired_stmt = select(func.count(HospitalSubscription.id)).where(
            HospitalSubscription.status.in_(["EXPIRED", "CANCELLED"])
        )

        total = (await self.db.execute(total_stmt)).scalar() or 0
        active = (await self.db.execute(active_stmt)).scalar() or 0
        expired = (await self.db.execute(expired_stmt)).scalar() or 0

        return {
            "total_subscriptions": int(total),
            "active_subscriptions": int(active),
            "expired_subscriptions": int(expired),
        }

    # =========================================================
    # AI INSIGHTS
    # =========================================================
    async def get_ai_insights(self) -> Dict[str, Any]:
        reward_dist = await self.ai_repo.get_reward_distribution()
        active_donors = await self.ai_repo.get_active_donors_count()

        return {
            "reward_distribution": reward_dist,
            "active_donors": active_donors,
        }

    # =========================================================
    # DASHBOARD AGGREGATION
    # =========================================================
    async def get_dashboard(self) -> Dict[str, Any]:
        revenue = await self.get_revenue_metrics(1)
        payments = await self.get_payment_status_breakdown()
        wallet = await self.get_wallet_flow()
        donor = await self.get_donor_activity()
        subscriptions = await self.get_subscription_metrics()
        ai = await self.get_ai_insights()

        return {
            "revenue": revenue,
            "payments": payments,
            "wallet": wallet,
            "donor": donor,
            "subscriptions": subscriptions,
            "ai": ai,
            "generated_at": self._now().isoformat(),
        }

    # =========================================================
    # CUSTOM RANGE ANALYTICS
    # =========================================================
    async def custom_metrics(
        self,
        start: datetime,
        end: datetime,
    ) -> Dict[str, Any]:

        stmt = select(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
        ).where(
            Payment.created_at.between(start, end),
            Payment.status == PaymentStatus.SUCCESS,
        )

        revenue, count = (await self.db.execute(stmt)).one()

        revenue = float(revenue or 0)
        count = int(count or 0)

        return {
            "revenue": revenue,
            "transactions": count,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }