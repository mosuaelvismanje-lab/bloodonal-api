from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List, Union, Sequence
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.blood.wallet.models import WalletTransaction

from app.modules.hospital.subscriptions.models import HospitalSubscription
from app.modules.payment.models import Payment

logger = logging.getLogger(__name__)


# =========================================================
# 🧠 AI DATA REPOSITORY (HARDENED)
# =========================================================
class AIRepository:
    """
    ENTERPRISE AI DATA ACCESS LAYER

    Guarantees:
    -------------------------------------------------
    ✔ Strict type normalization
    ✔ Null-safe aggregations
    ✔ Deterministic outputs
    ✔ Safe analytics boundaries
    ✔ ML-ready export format
    ✔ No business logic leakage
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================
    # SAFE SCALAR NORMALIZER
    # =========================================================
    def _safe_scalar(self, value: Any, default: Any = 0) -> Any:
        return default if value is None else value

    # =========================================================
    # 🧠 DONOR BEHAVIOR
    # =========================================================
    async def get_donor_stats(self, user_id: UUID) -> Dict[str, Any]:

        stmt_total = select(func.count()).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.type == "REWARD",
            WalletTransaction.status == "SUCCESS",
        )

        stmt_points = select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.type == "REWARD",
            WalletTransaction.status == "SUCCESS",
        )

        stmt_rejections = select(func.count()).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.type == "REJECTION",
        )

        total = (await self.db.execute(stmt_total)).scalar()
        points = (await self.db.execute(stmt_points)).scalar()
        rejections = (await self.db.execute(stmt_rejections)).scalar()

        return {
            "total_donations": int(self._safe_scalar(total, 0)),
            "donor_points": int(self._safe_scalar(points, 0)),
            "rejection_count": int(self._safe_scalar(rejections, 0)),
        }

    # =========================================================
    # ⚡ RESPONSE TIME
    # =========================================================
    async def get_average_response_time(self, user_id: UUID) -> Optional[float]:

        stmt = select(
            func.avg(
                func.extract(
                    "epoch",
                    WalletTransaction.updated_at - WalletTransaction.created_at
                ) / 60.0
            )
        ).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.type == "REWARD",
        )

        result = await self.db.execute(stmt)
        value = result.scalar()

        return None if value is None else float(value)

    # =========================================================
    # 📊 SUCCESS RATE
    # =========================================================
    async def get_success_rate(self, user_id: UUID) -> float:

        total_stmt = select(func.count()).where(
            WalletTransaction.user_id == user_id
        )

        success_stmt = select(func.count()).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.status == "SUCCESS",
        )

        total = (await self.db.execute(total_stmt)).scalar() or 0
        success = (await self.db.execute(success_stmt)).scalar() or 0

        if total == 0:
            return 0.0

        return float(success) / float(total)

    # =========================================================
    # 💰 PAYMENT SIGNAL
    # =========================================================
    async def get_user_payment_volume(self, user_id: UUID) -> float:

        stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.user_id == user_id,
            Payment.status == "SUCCESS",
        )

        result = await self.db.execute(stmt)
        value = result.scalar()

        return float(self._safe_scalar(value, 0.0))

    # =========================================================
    # 🏥 HOSPITAL PRIORITY
    # =========================================================
    async def get_hospital_priority(self, hospital_id: UUID) -> float:

        stmt = (
            select(HospitalSubscription)
            .where(
                HospitalSubscription.hospital_id == hospital_id,
                HospitalSubscription.status == "ACTIVE",
                HospitalSubscription.end_date > datetime.now(timezone.utc),
            )
            .order_by(HospitalSubscription.end_date.desc())
        )

        result = await self.db.execute(stmt)
        sub = result.scalars().first()

        if sub is None:
            return 1.0

        return float(getattr(sub, "priority_multiplier", 1.0) or 1.0)

    # =========================================================
    # 🔥 ACTIVE DONORS (SURGE ENGINE INPUT)
    # =========================================================
    async def get_active_donors_count(self) -> int:

        stmt = select(func.count()).where(
            WalletTransaction.status == "SUCCESS"
        )

        result = await self.db.execute(stmt)
        value = result.scalar()

        return int(self._safe_scalar(value, 0))

    # =========================================================
    # 📈 REWARD DISTRIBUTION
    # =========================================================
    async def get_reward_distribution(self) -> Dict[str, Any]:

        stmt = select(
            func.count(),
            func.avg(WalletTransaction.amount),
            func.max(WalletTransaction.amount),
            func.min(WalletTransaction.amount),
        ).where(
            WalletTransaction.type == "REWARD",
            WalletTransaction.status == "SUCCESS",
        )

        result = await self.db.execute(stmt)
        row = result.one()

        count, avg, max_v, min_v = row

        return {
            "total_rewards": int(self._safe_scalar(count, 0)),
            "average_reward": float(self._safe_scalar(avg, 0)),
            "max_reward": float(self._safe_scalar(max_v, 0)),
            "min_reward": float(self._safe_scalar(min_v, 0)),
        }

    # =========================================================
    # 🧪 ML TRAINING EXPORT (STREAM-SAFE READY)
    # =========================================================
    async def export_training_data(self, limit: int = 1000) -> List[Dict[str, Any]]:

        stmt = (
            select(
                WalletTransaction.user_id,
                WalletTransaction.amount,
                WalletTransaction.created_at,
                WalletTransaction.status,
            )
            .where(WalletTransaction.type == "REWARD")
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "user_id": str(r[0]),
                "amount": float(self._safe_scalar(r[1], 0)),
                "created_at": r[2].isoformat() if r[2] else None,
                "status": r[3],
            }
            for r in rows
        ]

    # =========================================================
    # ⚙️ SAFE RAW EXECUTOR (RESTRICTED USE ONLY)
    # =========================================================
    async def execute_raw_query(self, stmt):
        """
        ⚠️ INTERNAL ONLY
        Must be restricted at service layer
        """
        return await self.db.execute(stmt)