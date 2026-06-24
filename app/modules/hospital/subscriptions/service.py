from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.hospital.subscriptions.models import (
    HospitalSubscription,
    SubscriptionPlan,
)
from app.modules.hospital.subscriptions.repository import SubscriptionRepository
from app.modules.payment.models import PaymentStatus
from app.repositories.payment_repo import PaymentRepository


logger = logging.getLogger(__name__)


class SubscriptionService:
    """
    Production-grade subscription service.

    Responsibilities:
    -------------------------------------------------
    ✔ Plan validation
    ✔ Subscription lifecycle (create, activate, cancel, renew)
    ✔ Payment orchestration (idempotent-safe)
    ✔ Expiry handling
    ✔ Priority multiplier logic
    """

    def __init__(self):
        self.repo = SubscriptionRepository()

    # =========================================================
    # CREATE SUBSCRIPTION
    # =========================================================
    async def create_subscription(
        self,
        db: AsyncSession,
        hospital_id: UUID,
        plan_id: UUID,
        idempotency_key: Optional[str] = None,
    ) -> dict:

        plan: SubscriptionPlan | None = await self.repo.get_plan(db, plan_id)

        if not plan or not plan.is_active:
            raise ValueError("Invalid or inactive plan")

        existing = await self.repo.get_active_subscription(db, hospital_id)
        if existing:
            raise ValueError("Hospital already has an active subscription")

        now = datetime.now(timezone.utc)

        # =====================================================
        # FREE PLAN
        # =====================================================
        if float(plan.price) <= 0:
            subscription = await self.repo.create_subscription(
                db=db,
                hospital_id=hospital_id,
                plan_id=plan.id,
                status="ACTIVE",
                start_date=now,
                end_date=now + timedelta(days=plan.duration_days),
                auto_renew=False,
                payment_reference=None,
            )

            return {"subscription": subscription, "payment": None}

        # =====================================================
        # PAID PLAN FLOW
        # =====================================================
        payment_repo = PaymentRepository(db)

        if idempotency_key:
            existing_payment = await payment_repo.get_by_idempotency(idempotency_key)
            if existing_payment:
                return {
                    "subscription": None,
                    "payment": existing_payment,
                }

        payment = await payment_repo.create_payment(
            user_id=hospital_id,
            payment_type="SUBSCRIPTION",
            amount=float(plan.price),
            idempotency_key=idempotency_key,
            details={"plan_id": str(plan.id)},
        )

        subscription = await self.repo.create_subscription(
            db=db,
            hospital_id=hospital_id,
            plan_id=plan.id,
            status="PENDING",
            start_date=None,
            end_date=None,
            auto_renew=False,
            payment_reference=str(payment.id),
        )

        logger.info(
            "[SUBSCRIPTION_CREATED] hospital=%s plan=%s status=PENDING",
            hospital_id,
            plan.name,
        )

        return {"subscription": subscription, "payment": payment}

    # =========================================================
    # ACTIVATE AFTER PAYMENT
    # =========================================================
    async def activate_subscription(
        self,
        db: AsyncSession,
        payment_reference: str,
    ) -> Optional[HospitalSubscription]:

        payment_repo = PaymentRepository(db)

        payment = await payment_repo.get_payment_by_id(UUID(payment_reference))
        if not payment or payment.status != PaymentStatus.SUCCESS:
            return None

        subscription = await self.repo.get_by_payment_reference(
            db, payment_reference
        )

        if not subscription:
            return None

        if subscription.status == "ACTIVE":
            return subscription

        plan = await self.repo.get_plan(db, subscription.plan_id)
        now = datetime.now(timezone.utc)

        subscription.status = "ACTIVE"
        subscription.start_date = now
        subscription.end_date = now + timedelta(days=plan.duration_days)

        await db.flush()

        logger.info("[SUBSCRIPTION_ACTIVATED] %s", subscription.id)

        return subscription

    # =========================================================
    # CANCEL
    # =========================================================
    async def cancel_subscription(
        self,
        db: AsyncSession,
        hospital_id: UUID,
    ) -> Optional[HospitalSubscription]:

        subscription = await self.repo.get_active_subscription(db, hospital_id)

        if not subscription:
            return None

        subscription.status = "CANCELLED"
        subscription.auto_renew = False

        await db.flush()

        logger.info("[SUBSCRIPTION_CANCELLED] %s", subscription.id)

        return subscription

    # =========================================================
    # RENEW
    # =========================================================
    async def renew_subscription(
        self,
        db: AsyncSession,
        hospital_id: UUID,
    ) -> Optional[HospitalSubscription]:

        subscription = await self.repo.get_active_subscription(db, hospital_id)

        if not subscription:
            return None

        plan = await self.repo.get_plan(db, subscription.plan_id)

        subscription.end_date = subscription.end_date + timedelta(
            days=plan.duration_days
        )

        await db.flush()

        logger.info("[SUBSCRIPTION_RENEWED] %s", subscription.id)

        return subscription

    # =========================================================
    # EXPIRE (CRON)
    # =========================================================
    async def expire_subscriptions(self, db: AsyncSession) -> int:

        expired = await self.repo.expire_old_subscriptions(db)

        if expired:
            logger.info("[SUBSCRIPTION_EXPIRED] count=%s", expired)

        return expired

    # =========================================================
    # PRIORITY MULTIPLIER
    # =========================================================
    async def get_priority_multiplier(
        self,
        db: AsyncSession,
        hospital_id: UUID,
    ) -> float:

        subscription = await self.repo.get_active_subscription(db, hospital_id)

        if not subscription:
            return 1.0

        plan = await self.repo.get_plan(db, subscription.plan_id)

        return float(plan.priority_multiplier or 1.0)