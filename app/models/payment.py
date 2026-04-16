from __future__ import annotations

import uuid
import enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import (
    String,
    DateTime,
    Numeric,
    JSON,
    Index,
    func,
    Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# ----------------------------
# Enums for Strict Validation
# ----------------------------

class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"  # Created, waiting for USSD/SMS
    SUCCESS = "SUCCESS"  # Confirmed by transaction listener/admin
    FAILED = "FAILED"  # Explicitly rejected
    EXPIRED = "EXPIRED"  # Cleanup worker marked as too old
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"  # Manual intervention needed


class PaymentProvider(str, enum.Enum):
    MTN = "MTN"
    ORANGE = "ORANGE"
    WALLET = "WALLET"  # Internal Bloodonal Wallet
    STRIPE = "STRIPE"  # If expanding in 2026


class ServiceType(str, enum.Enum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    TAXI = "taxi"
    BIKER = "biker"
    BLOOD_REQUEST = "blood_request"
    CONSULTATION = "consultation"


# ----------------------------
# Payment Model (SQLAlchemy 2.0)
# ----------------------------

class Payment(Base):
    __tablename__ = "payments"

    # 1. Identity & Reference
    # Primary key uses UUID for high security and distributed DB compatibility
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Safe public reference (e.g., BLD-2026-XXXX)
    reference: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # 2. User & Ownership
    user_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # 3. Context & Money
    service_type: Mapped[ServiceType] = mapped_column(
        SAEnum(ServiceType, native_enum=False), nullable=False
    )

    # Numeric precision (10,2) is safe, though XAF is usually whole numbers
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="XAF", nullable=False)

    # 4. Gateway & SMS Logic
    provider: Mapped[PaymentProvider] = mapped_column(
        SAEnum(PaymentProvider, native_enum=False), nullable=False
    )
    # The SMS transaction ID from MTN/Orange (vital for the bypass logic)
    provider_tx_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # 5. Security & Idempotency
    # Prevents "double-click" payment processing
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    # HMAC signature for verifying request integrity
    signature: Mapped[str] = mapped_column(String(255), nullable=False)

    # 6. Status Lifecycle
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )

    # 7. Timing & Auditing
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 8. Dynamic Metadata
    # Stores USSD strings, agent info, or raw SMS snippets for debugging
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # ----------------------------
    # Helpers
    # ----------------------------
    @property
    def is_paid(self) -> bool:
        return self.status == PaymentStatus.SUCCESS

    @property
    def is_active(self) -> bool:
        """Checks if the payment is still valid for processing."""
        return self.status == PaymentStatus.PENDING and self.expires_at > datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"<Payment(ref={self.reference}, status={self.status}, amount={self.amount})>"
        )


# ----------------------------
# Composite Indexes (Performance Audit)
# ----------------------------

# Quick lookup for user payment history filtered by service
Index("ix_payments_user_history", Payment.user_id, Payment.service_type, Payment.created_at)

# Optimization for the Background Janitor (finds expired PENDING payments)
Index("ix_payments_janitor_sweep", Payment.status, Payment.expires_at)

# High-speed check for existing provider IDs to prevent fraud
Index("ix_payments_duplicate_tx_check", Payment.provider, Payment.provider_tx_id)