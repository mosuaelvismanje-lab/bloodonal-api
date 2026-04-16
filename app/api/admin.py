import logging
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

# ✅ Standardized Dependencies
from app.api.dependencies import get_admin_user, get_db_session
from app.models.payment import Payment, PaymentStatus
from app.models.call_session import CallSession, CallStatus

# ✅ Core Services & Repositories
from app.services.orchestrator import service_orchestrator
from app.services.stats_service import StatsService
from app.services.registry import registry
from app.repositories.payment_repo import PaymentRepository

from app.schemas.payment_admin import (
    AdminConfirmPaymentRequest,
    AdminPaymentActionResponse,
    PaymentDashboardSummary,
    DetailedPaymentReport,
    ActiveCallReport
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin Operations"])

# ---------------------------------------------------------
# 1. ENHANCED DASHBOARD STATS
# ---------------------------------------------------------

@router.get("/dashboard-stats", response_model=PaymentDashboardSummary)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(get_admin_user)
):
    """
    Unified Dashboard: Aggregates revenue and pending verifications.
    """
    metrics = await StatsService.get_dashboard_metrics(db)

    # Use specialized group-by logic for service revenue
    consultation_stmt = select(func.sum(Payment.amount)).where(
        Payment.status == PaymentStatus.SUCCESS,
        Payment.payment_type.in_(["doctor", "nurse"])
    )
    res = await db.execute(consultation_stmt)
    consultation_revenue = res.scalar() or 0.0

    return PaymentDashboardSummary(
        total_awaiting_verification=metrics["total_awaiting_verification"],
        total_revenue_today=metrics["total_revenue_today"],
        consultation_revenue_total=consultation_revenue,
        bypass_matches_today=metrics["bypass_matches_today"],
        mtn_volume_today=metrics.get("mtn_volume", 0.0),
        orange_volume_today=metrics.get("orange_volume", 0.0)
    )

# ---------------------------------------------------------
# 2. CALL MONITORING (Live Emergency Watch)
# ---------------------------------------------------------

@router.get("/active-calls", response_model=List[ActiveCallReport])
async def monitor_live_calls(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(get_admin_user)
):
    """
    Emergency Monitor: Real-time view of ongoing calls across the platform.
    """
    stmt = (
        select(CallSession)
        .where(CallSession.status == CallStatus.ONGOING)
        .order_by(CallSession.started_at.desc())
    )
    result = await db.execute(stmt)
    calls = result.scalars().all()

    return [
        ActiveCallReport(
            session_id=str(c.id),
            caller_id=c.caller_id,
            callee_id=c.callee_id,
            service_type=c.callee_type,
            duration_current=int((datetime.now(timezone.utc) - c.started_at).total_seconds())
        ) for c in calls
    ]

# ---------------------------------------------------------
# 3. PAYMENT VERIFICATION (The Orchestrator Hub)
# ---------------------------------------------------------

@router.post("/verify-bypass", response_model=AdminPaymentActionResponse)
async def verify_payment_override(
    req: AdminConfirmPaymentRequest,
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(get_admin_user)
):
    """
    Admin Override: Manually verifies a payment and triggers automated service activation.
    """
    payment_repo = PaymentRepository(db)

    # 1. Find the pending record via Repository
    stmt = (
        select(Payment)
        .where(
            Payment.status == PaymentStatus.PENDING,
            Payment.amount == req.amount,
            # metadata search for phone stored during initiate_payment
            Payment.metadata['phone'].astext == req.payer_phone
        )
        .order_by(Payment.created_at.desc())
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(status_code=404, detail="No matching pending payment found.")

    # 2. Update status with Repository State Guard (prevents double SUCCESS)
    updated_payment = await payment_repo.update_status(
        payment_id=payment.id,
        new_status=PaymentStatus.SUCCESS,
        provider_tx_id=req.transaction_id
    )

    if not updated_payment:
        raise HTTPException(status_code=400, detail="Transaction ID already verified or payment finalized.")

    # 3. Add Audit Metadata
    meta = updated_payment.metadata or {}
    meta.update({"verified_by": admin.email, "mode": "admin_bypass"})
    updated_payment.metadata = meta

    # 4. 🚀 Trigger Domain Orchestration
    # This activates the Listing, sends FCM alerts, and logs the Quota use
    await service_orchestrator.activate_listing(
        db=db,
        user_id=updated_payment.user_id,
        service_type=updated_payment.payment_type,
        activation_ref=updated_payment.idempotency_key
    )

    await db.commit()
    return AdminPaymentActionResponse(
        success=True,
        reference=str(updated_payment.id),
        message=f"Service {updated_payment.payment_type} activated via Admin bypass."
    )

# ---------------------------------------------------------
# 4. AUDIT LOGS
# ---------------------------------------------------------

@router.get("/recent-payments", response_model=List[DetailedPaymentReport])
async def get_recent_payments(
    db: AsyncSession = Depends(get_db_session),
    admin=Depends(get_admin_user)
):
    """Historical Audit with human-readable service mapping from Registry."""
    stmt = select(Payment).order_by(Payment.created_at.desc()).limit(50)
    result = await db.execute(stmt)
    payments = result.scalars().all()

    report = []
    for p in payments:
        meta = registry.get_service_meta(p.payment_type)
        report.append(DetailedPaymentReport(
            reference=str(p.id),
            amount=p.amount,
            status=p.status,
            service_display_name=meta.get("display_name", p.payment_type),
            user_phone=p.metadata.get("phone", "N/A") if p.metadata else "N/A",
            created_at=p.created_at
        ))

    return report