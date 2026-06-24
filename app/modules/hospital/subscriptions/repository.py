from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hospital.subscriptions.models import (
    HospitalSubscription,
    SubscriptionPlan,
)

logger = logging.getLogger(__name__)


class SubscriptionRepository:
    """
    Subscription persistence layer.

    Responsibilities:
    -------------------------------------------------
    ✔ Subscription CRUD
    ✔ Plan retrieval
    ✔ Active subscription lookup
    ✔ Expiry management
    ✔ Payment reference linking
    """

    # =========================================================
    # PLANS
    # =========================================================
    async def get_plan(
        self,
        db: AsyncSession,
        plan_id: UUID,
    ) -> Optional[SubscriptionPlan]:

        stmt = select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_plans(
        self,
        db: AsyncSession,
    ) -> List[SubscriptionPlan]:

        stmt = select(SubscriptionPlan).where(
            SubscriptionPlan.is_active == True  # noqa
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # =========================================================
    # SUBSCRIPTION LOOKUPS
    # =========================================================
    async def get_by_id(
        self,
        db: AsyncSession,
        subscription_id: UUID,
    ) -> Optional[HospitalSubscription]:

        stmt = select(HospitalSubscription).where(
            HospitalSubscription.id == subscription_id
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_payment_reference(
        self,
        db: AsyncSession,
        payment_reference: str,
    ) -> Optional[HospitalSubscription]:

        stmt = select(HospitalSubscription).where(
            HospitalSubscription.payment_reference == payment_reference
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_subscription(
        self,
        db: AsyncSession,
        hospital_id: UUID,
    ) -> Optional[HospitalSubscription]:

        now = datetime.now(timezone.utc)

        stmt = select(HospitalSubscription).where(
            HospitalSubscription.hospital_id == hospital_id,
            HospitalSubscription.status == "ACTIVE",
            HospitalSubscription.end_date > now,
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================
    # CREATE
    # =========================================================
    async def create_subscription(
        self,
        db: AsyncSession,
        hospital_id: UUID,
        plan_id: UUID,
        status: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        auto_renew: bool,
        payment_reference: Optional[str] = None,
        snapshot: Optional[dict] = None,
    ) -> HospitalSubscription:

        subscription = HospitalSubscription(
            hospital_id=hospital_id,
            plan_id=plan_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            auto_renew=auto_renew,
            payment_reference=payment_reference,
            snapshot=snapshot,
        )

        db.add(subscription)
        await db.flush()

        logger.info(
            "[SUBSCRIPTION_REPO] created id=%s hospital=%s",
            subscription.id,
            hospital_id,
        )

        return subscription

    # =========================================================
    # UPDATE STATUS
    # =========================================================
    async def update_status(
        self,
        db: AsyncSession,
        subscription_id: UUID,
        status: str,
    ) -> Optional[HospitalSubscription]:

        stmt = (
            update(HospitalSubscription)
            .where(HospitalSubscription.id == subscription_id)
            .values(status=status, updated_at=datetime.now(timezone.utc))
            .returning(HospitalSubscription)
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    # =========================================================
    # EXPIRY HANDLING
    # =========================================================
    async def expire_old_subscriptions(self, db: AsyncSession) -> int:

        now = datetime.now(timezone.utc)

        stmt = (
            update(HospitalSubscription)
            .where(
                HospitalSubscription.status == "ACTIVE",
                HospitalSubscription.end_date <= now,
            )
            .values(
                status="EXPIRED",
                updated_at=now,
            )
        )

        result = await db.execute(stmt)
        await db.flush()

        expired_count = result.rowcount or 0

        logger.info(
            "[SUBSCRIPTION_REPO] expired=%s subscriptions",
            expired_count,
        )

        return expired_count

    # =========================================================
    # ACTIVATE VIA PAYMENT
    # =========================================================
    async def activate_by_payment(
        self,
        db: AsyncSession,
        subscription: HospitalSubscription,
        start_date: datetime,
        end_date: datetime,
    ) -> HospitalSubscription:

        subscription.status = "ACTIVE"
        subscription.start_date = start_date
        subscription.end_date = end_date
        subscription.updated_at = datetime.now(timezone.utc)

        await db.flush()

        logger.info(
            "[SUBSCRIPTION_REPO] activated id=%s",
            subscription.id,
        )

        return subscription

    # =========================================================
    # CANCEL
    # =========================================================
    async def cancel_subscription(
        self,
        db: AsyncSession,
        hospital_id: UUID,
    ) -> Optional[HospitalSubscription]:

        subscription = await self.get_active_subscription(db, hospital_id)

        if not subscription:
            return None

        subscription.status = "CANCELLED"
        subscription.auto_renew = False
        subscription.updated_at = datetime.now(timezone.utc)

        await db.flush()

        logger.info(
            "[SUBSCRIPTION_REPO] cancelled id=%s",
            subscription.id,
        )

        return subscription

    # =========================================================
    # RENEW
    # =========================================================
    async def extend_subscription(
        self,
        db: AsyncSession,
        subscription: HospitalSubscription,
        extra_days: int,
    ) -> HospitalSubscription:

        if subscription.end_date is None:
            raise ValueError("Subscription has no end_date")

        subscription.end_date = subscription.end_date + timedelta(days=extra_days)
        subscription.updated_at = datetime.now(timezone.utc)

        await db.flush()

        logger.info(
            "[SUBSCRIPTION_REPO] extended id=%s days=%s",
            subscription.id,
            extra_days,
        )

        return subscription

    # =========================================================
    # METRICS
    # =========================================================
    async def count_by_status(
        self,
        db: AsyncSession,
    ) -> dict:

        stmt = select(
            HospitalSubscription.status,
            func.count(HospitalSubscription.id),
        ).group_by(HospitalSubscription.status)

        result = await db.execute(stmt)

        return {
            status: int(count)
            for status, count in result.all()
        }