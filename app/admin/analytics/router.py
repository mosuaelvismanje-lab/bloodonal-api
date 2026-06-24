from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException, status

from sqlalchemy.ext.asyncio import AsyncSession

# 🔗 Core dependencies
from app.api.dependencies import get_db_session, get_current_user

# 🔗 Service
from app.admin.analytics.service import AnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/analytics",
    tags=["Admin Analytics"],
)


# =========================================================
# 🔐 ADMIN GUARD (UPGRADE READY)
# =========================================================
def require_admin(user=Depends(get_current_user)):
    """
    Basic admin protection.

    Upgrade later to:
    - Role-based access control (RBAC)
    - Permission scopes (analytics:read, analytics:write)
    """
    if not getattr(user, "is_admin", False):
        logger.warning("🚫 Unauthorized analytics access attempt by user=%s", getattr(user, "id", None))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# =========================================================
# 🔧 SERVICE FACTORY (avoids repetition)
# =========================================================
def get_service(db: AsyncSession) -> AnalyticsService:
    return AnalyticsService(db)


# =========================================================
# 📊 FULL DASHBOARD
# =========================================================
@router.get("/dashboard", response_model=Dict[str, Any])
async def get_dashboard(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    """
    All-in-one admin dashboard

    Includes:
    - revenue
    - payments
    - wallet flow
    - donor activity
    - subscriptions
    - AI insights
    """
    service = get_service(db)

    try:
        data = await service.get_dashboard()
        logger.info("📊 Dashboard loaded by admin=%s", getattr(admin, "id", None))
        return data

    except Exception as e:
        logger.exception("❌ Dashboard fetch failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to load dashboard",
        ) from e


# =========================================================
# 💰 REVENUE
# =========================================================
@router.get("/revenue", response_model=Dict[str, Any])
async def get_revenue(
    days: int = Query(1, ge=1, le=365),
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    service = get_service(db)

    try:
        return await service.get_revenue_metrics(days=days)
    except Exception as e:
        logger.exception("❌ Revenue fetch failed")
        raise HTTPException(status_code=500, detail="Revenue fetch failed") from e


# =========================================================
# 📊 PAYMENT STATUS
# =========================================================
@router.get("/payments/status", response_model=Dict[str, int])
async def payment_status_breakdown(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    service = get_service(db)

    try:
        return await service.get_payment_status_breakdown()
    except Exception as e:
        logger.exception("❌ Payment breakdown failed")
        raise HTTPException(status_code=500, detail="Payment breakdown failed") from e


# =========================================================
# 💸 WALLET FLOW
# =========================================================
@router.get("/wallet/flow", response_model=Dict[str, Any])
async def wallet_flow(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    service = get_service(db)

    try:
        return await service.get_wallet_flow()
    except Exception as e:
        logger.exception("❌ Wallet flow failed")
        raise HTTPException(status_code=500, detail="Wallet flow fetch failed") from e


# =========================================================
# 🧠 DONOR ANALYTICS
# =========================================================
@router.get("/donor", response_model=Dict[str, Any])
async def donor_analytics(
    user_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    service = get_service(db)

    try:
        return await service.get_donor_activity(user_id=user_id)
    except Exception as e:
        logger.exception("❌ Donor analytics failed")
        raise HTTPException(status_code=500, detail="Donor analytics failed") from e


# =========================================================
# 🏥 SUBSCRIPTIONS
# =========================================================
@router.get("/subscriptions", response_model=Dict[str, Any])
async def subscription_metrics(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    service = get_service(db)

    try:
        return await service.get_subscription_metrics()
    except Exception as e:
        logger.exception("❌ Subscription metrics failed")
        raise HTTPException(status_code=500, detail="Subscription metrics failed") from e


# =========================================================
# 🤖 AI INSIGHTS
# =========================================================
@router.get("/ai", response_model=Dict[str, Any])
async def ai_insights(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    service = get_service(db)

    try:
        return await service.get_ai_insights()
    except Exception as e:
        logger.exception("❌ AI insights failed")
        raise HTTPException(status_code=500, detail="AI insights failed") from e


# =========================================================
# 📈 CUSTOM RANGE METRICS
# =========================================================
@router.get("/custom", response_model=Dict[str, Any])
async def custom_metrics(
    start: datetime = Query(..., description="Start datetime (ISO format)"),
    end: datetime = Query(..., description="End datetime (ISO format)"),
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(require_admin),
):
    if start >= end:
        raise HTTPException(
            status_code=400,
            detail="Invalid date range: start must be before end",
        )

    # Optional safety: prevent insane queries
    if (end - start).days > 365:
        raise HTTPException(
            status_code=400,
            detail="Date range too large (max 365 days)",
        )

    service = get_service(db)

    try:
        return await service.custom_metrics(start=start, end=end)
    except Exception as e:
        logger.exception("❌ Custom metrics failed")
        raise HTTPException(status_code=500, detail="Custom metrics failed") from e