from fastapi import APIRouter, Query, Depends
from typing import Optional
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.api.deps import get_db
from app.models.payment import Payment, PaymentStatus
from app.schemas.payment_dashboard import PaymentListResponse, PaymentItem

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


@router.get("/payments", response_model=PaymentListResponse)
async def list_payments(
    status: Optional[PaymentStatus] = Query(None),
    provider: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a paginated list of payments for admin dashboard.
    Supports filtering by status and payment provider.
    """

    # 1️⃣ Base query
    stmt = select(Payment)

    # 2️⃣ Apply filters
    if status:
        stmt = stmt.where(Payment.status == status)
    if provider:
        stmt = stmt.where(Payment.provider == provider)

    # 3️⃣ Total count for pagination
    total = await db.scalar(
        select(func.count()).select_from(stmt.subquery())
    )

    # 4️⃣ Apply ordering and pagination
    stmt = stmt.order_by(desc(Payment.created_at)).limit(limit).offset(offset)

    # 5️⃣ Execute query
    result = await db.execute(stmt)
    payments = result.scalars().all()

    # 6️⃣ Map ORM Payment -> Pydantic PaymentItem
    items = [
        PaymentItem(
            id=str(p.id),
            user_id=p.user_id,
            payer_phone=getattr(p, "user_phone", None),  # For manual USSD verification
            amount=float(p.amount),
            currency=getattr(p, "currency", "XAF"),
            status=p.status,
            transaction_id=getattr(p, "internal_tx_id", None),
            created_at=p.created_at,
        )
        for p in payments
    ]

    # 7️⃣ Return response
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    }
