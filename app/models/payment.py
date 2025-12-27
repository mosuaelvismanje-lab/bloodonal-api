from __future__ import annotations

import uuid
from enum import Enum as PyEnum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Numeric,
    JSON,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Enum as SAEnum
from sqlalchemy.sql import func

from app.database import Base


# ----------------------------
# Payment Status
# ----------------------------
class PaymentStatus(PyEnum):
    PENDING = "PENDING"                  # Created, waiting for USSD confirmation
    SUCCESS = "SUCCESS"                  # Confirmed by admin/agent
    FAILED = "FAILED"                    # Expired / rejected
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"  # New, pending admin confirmation


# ----------------------------
# Payment Model
# ----------------------------
class Payment(Base):
    __tablename__ = "payments"

    # Primary key (internal)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # External reference (safe to expose)
    reference = Column(String, nullable=False, unique=True, index=True)

    # User info
    user_id = Column(String, nullable=False, index=True)
    user_phone = Column(String, nullable=False, index=True)

    # Service context
    service_type = Column(
        String,
        nullable=False,
        comment="doctor | nurse | taxi | biker | blood_request | etc"
    )

    # Money
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(8), nullable=False, default="XAF")

    # Payment gateway
    provider = Column(String, nullable=False)                  # MTN | ORANGE
    provider_tx_id = Column(String, nullable=True, index=True) # SMS transaction ID

    # Security / integrity
    signature = Column(String, nullable=False)

    # Idempotency (prevents double charge)
    idempotency_key = Column(String, nullable=False, unique=True, index=True)

    # Status lifecycle
    status = Column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )

    # Timing / lifecycle
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When a pending payment becomes invalid"
    )

    confirmed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Set when admin confirms payment"
    )

    # Extra metadata (USSD string, agent name, failure reason, raw SMS, etc)
    metadata_json = Column(JSON, nullable=True)

    # Audit timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    # ----------------------------
    # Helpers
    # ----------------------------
    @property
    def is_paid(self) -> bool:
        return self.status == PaymentStatus.SUCCESS

    @property
    def is_awaiting_verification(self) -> bool:
        return self.status == PaymentStatus.AWAITING_VERIFICATION

    def __repr__(self) -> str:
        return (
            f"<Payment id={self.id} ref={self.reference} "
            f"user_phone={self.user_phone} amount={self.amount} "
            f"provider={self.provider} status={self.status}>"
        )


# ----------------------------
# Indexes (Performance)
# ----------------------------
Index(
    "ix_payments_user_service_created",
    Payment.user_id,
    Payment.service_type,
    Payment.created_at,
)

Index(
    "ix_payments_provider_status",
    Payment.provider,
    Payment.status,
)

Index(
    "ix_payments_expiry_pending",
    Payment.status,
    Payment.expires_at,
)
