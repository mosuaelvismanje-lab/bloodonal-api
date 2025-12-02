# app/models/payment.py
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

# import the project's Base so Alembic sees a single MetaData
from app.database import Base


class PaymentStatus(PyEnum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class Payment(Base):
    __tablename__ = "payments"

    # Primary key as UUID
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Who paid / for which service
    user_id = Column(String, nullable=False, index=True)
    service_type = Column(String, nullable=False)  # e.g. "doctor", "nurse", "taxi", "biker", "blood_request"

    # Money fields
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(length=8), nullable=False, default="XAF")

    # Status (store as VARCHAR via native_enum=False to avoid DB enum objects by default)
    status = Column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False),
        nullable=False,
        default=PaymentStatus.PENDING,
    )

    # Idempotency / dedupe
    idempotency_key = Column(String, nullable=False, unique=True, index=True)

    # Provider info (stripe/flutterwave/mtn/etc)
    provider = Column(String, nullable=False)
    provider_tx_id = Column(String, nullable=True, index=True)

    # NOTE: do NOT name this attribute `metadata` (reserved on declarative models)
    metadata_json = Column(JSON, nullable=True)

    # Timestamps - use DB-side default for consistency
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # helpful repr
    def __repr__(self) -> str:
        return f"<Payment id={self.id} user={self.user_id} service={self.service_type} amount={self.amount} status={self.status}>"

    # optional convenience helpers
    @property
    def is_paid(self) -> bool:
        return self.status == PaymentStatus.SUCCESS

# useful composite/indexes (optional)
Index("ix_payments_user_service_created", Payment.user_id, Payment.service_type, Payment.created_at)
