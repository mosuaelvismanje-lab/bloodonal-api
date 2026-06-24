

import logging
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession

# 🔐 Auth + DB
from app.api.dependencies import get_current_user, get_db_session

# 🧠 Service
from app.modules.hospital.subscriptions.service import SubscriptionService

# 📦 Schemas
from app.modules.hospital.subscriptions.schemas import (
    SubscriptionCreateRequest,
    SubscriptionCreateResponse,
    SubscriptionResponse,
    SubscriptionListResponse,
    SubscriptionWithPlanResponse,
    SuccessResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/hospital/subscriptions",
    tags=["Hospital Subscriptions"],
)

service = SubscriptionService()


# =========================================================
# 🏥 SUBSCRIBE TO PLAN
# =========================================================
@router.post(
    "/subscribe",
    response_model=SubscriptionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe_to_plan(
    req: SubscriptionCreateRequest,
    idempotency_key: str = Header(..., alias="X-Idempotency-Key"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create a hospital subscription.

    Flow:
    - FREE → instant activation
    - PAID → returns payment reference + USSD
    """

    try:
        result = await service.create_subscription(
            db=db,
            hospital_id=user.uid,
            plan_id=req.plan_id,
            idempotency_key=idempotency_key,
        )

        await db.commit()

        subscription = result.get("subscription")
        payment = result.get("payment")

        # FREE plan
        if subscription and not payment:
            return SubscriptionCreateResponse(
                subscription_id=subscription.id,
                status=subscription.status,
                payment_reference=None,
                payment_status="SUCCESS",
            )

        # PAID plan
        if payment:
            return SubscriptionCreateResponse(
                subscription_id=subscription.id if subscription else None,
                status="PENDING",
                payment_reference=str(payment.id),
                payment_status=payment.status,
                ussd_string=f"*126*9*XXXX*{int(payment.amount)}#",  # 🔥 plug real generator
            )

        raise HTTPException(
            status_code=400,
            detail="Subscription creation failed",
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception("Subscription creation failed")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


# =========================================================
# 📊 GET ACTIVE SUBSCRIPTION
# =========================================================
@router.get(
    "/me",
    response_model=SubscriptionWithPlanResponse,
)
async def get_my_subscription(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    subscription = await service.repo.get_active_subscription(db, user.uid)

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="No active subscription",
        )

    plan = await service.repo.get_plan(db, subscription.plan_id)

    return SubscriptionWithPlanResponse(
        id=subscription.id,
        hospital_id=subscription.hospital_id,
        status=subscription.status,
        start_date=subscription.start_date,
        end_date=subscription.end_date,
        auto_renew=subscription.auto_renew,
        plan=plan,
    )


# =========================================================
# 📜 LIST SUBSCRIPTIONS
# =========================================================
@router.get(
    "/list",
    response_model=SubscriptionListResponse,
)
async def list_subscriptions(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    subs = await service.repo.list_subscriptions(db, user.uid)

    return SubscriptionListResponse(data=subs)


# =========================================================
# ❌ CANCEL SUBSCRIPTION
# =========================================================
@router.post(
    "/cancel",
    response_model=SuccessResponse,
)
async def cancel_subscription(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    subscription = await service.cancel_subscription(db, user.uid)

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="No active subscription",
        )

    await db.commit()

    return SuccessResponse(message="Subscription cancelled")


# =========================================================
# 🔄 RENEW SUBSCRIPTION
# =========================================================
@router.post(
    "/renew",
    response_model=SubscriptionResponse,
)
async def renew_subscription(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    subscription = await service.renew_subscription(db, user.uid)

    if not subscription:
        raise HTTPException(
            status_code=404,
            detail="No active subscription",
        )

    await db.commit()

    return subscription


# =========================================================
# ⚡ GET PRIORITY MULTIPLIER (DEBUG / INTERNAL)
# =========================================================
@router.get("/priority")
async def get_priority(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    multiplier = await service.get_priority_multiplier(db, user.uid)

    return {
        "hospital_id": str(user.uid),
        "priority_multiplier": multiplier,
    }