from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    Numeric,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# =========================================================
# SUBSCRIPTION PLAN
# =========================================================
class SubscriptionPlan(Base):
    __tablename__ = "hospital_subscription_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="XAF")

    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_multiplier: Mapped[float] = mapped_column(default=1.0)

    features: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# =========================================================
# HOSPITAL SUBSCRIPTION
# =========================================================
class HospitalSubscription(Base):
    __tablename__ = "hospital_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        nullable=False,
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospital_subscription_plans.id"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="ACTIVE",
        index=True,
    )

    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)

    snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc),
    )


# =========================================================
# BILLING
# =========================================================
class SubscriptionBilling(Base):
    __tablename__ = "hospital_subscription_billings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        index=True,
        nullable=False,
    )

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hospital_subscriptions.id"),
        nullable=False,
    )

    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="XAF")

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        index=True,
    )

    provider_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # renamed from `metadata` because SQLAlchemy reserves that name
    billing_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# =========================================================
# INDEXES
# =========================================================
Index(
    "idx_hospital_active_subscription",
    HospitalSubscription.hospital_id,
    HospitalSubscription.status,
)

Index(
    "idx_subscription_expiry",
    HospitalSubscription.end_date,
)

Index(
    "idx_subscription_billing_status",
    SubscriptionBilling.status,
)