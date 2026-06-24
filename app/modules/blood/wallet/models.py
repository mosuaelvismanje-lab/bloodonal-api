from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Numeric,
    Index,
    Enum as SAEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


# =========================================================
# ENUMS
# =========================================================
class WalletOwnerType(str, enum.Enum):
    DONOR = "DONOR"
    HOSPITAL = "HOSPITAL"
    USER = "USER"
    DRIVER = "DRIVER"


class WalletTransactionType(str, enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    WITHDRAWAL = "WITHDRAWAL"
    REFUND = "REFUND"
    BONUS = "BONUS"
    SURGE = "SURGE"
    PAYMENT = "PAYMENT"


class WalletTransactionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class WalletPayoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"


class WalletPayoutMethod(str, enum.Enum):
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_TRANSFER = "BANK_TRANSFER"
    CRYPTO = "CRYPTO"


class BillingType(str, enum.Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    MATCHING = "MATCHING"
    PRIORITY_ACCESS = "PRIORITY_ACCESS"


class BillingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"


# =========================================================
# WALLET
# =========================================================
class Wallet(Base):
    """
    Enterprise wallet system.

    Features:
    -----------------------------------
    ✔ Ledger-compatible
    ✔ One wallet per owner
    ✔ Fraud lock support
    ✔ Financial audit ready
    ✔ Async-safe with SQLAlchemy 2.0
    """

    __tablename__ = "wallets"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =====================================================
    # OWNER
    # =====================================================
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    owner_type: Mapped[WalletOwnerType] = mapped_column(
        SAEnum(WalletOwnerType, name="wallet_owner_type"),
        nullable=False,
        index=True,
    )

    # =====================================================
    # FINANCIALS
    # =====================================================
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(10),
        default="XAF",
        nullable=False,
    )

    # =====================================================
    # STATUS CONTROL
    # =====================================================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # AUDIT
    # =====================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # =====================================================
    # RELATIONSHIPS
    # =====================================================
    transactions = relationship(
        "WalletTransaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )

    payouts = relationship(
        "WalletPayout",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )

    # =====================================================
    # INDEXES / CONSTRAINTS
    # =====================================================
    __table_args__ = (
        Index("idx_wallet_owner", "owner_id", "owner_type"),
        UniqueConstraint(
            "owner_id",
            "owner_type",
            name="uq_wallet_owner",
        ),
    )

    # =====================================================
    # HELPERS
    # =====================================================
    @property
    def is_usable(self) -> bool:
        return self.is_active and not self.is_locked

    def __repr__(self) -> str:
        return (
            f"<Wallet(id={self.id}, balance={self.balance}, "
            f"owner_type={self.owner_type})>"
        )


# =========================================================
# WALLET TRANSACTIONS
# =========================================================
class WalletTransaction(Base):
    """
    Immutable ledger entry.
    """

    __tablename__ = "wallet_transactions"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =====================================================
    # RELATION
    # =====================================================
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    wallet = relationship(
        "Wallet",
        back_populates="transactions",
    )

    # =====================================================
    # TRANSACTION DATA
    # =====================================================
    type: Mapped[WalletTransactionType] = mapped_column(
        SAEnum(WalletTransactionType, name="wallet_transaction_type"),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # =====================================================
    # REFERENCES
    # =====================================================
    reference_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # =====================================================
    # STATUS
    # =====================================================
    status: Mapped[WalletTransactionStatus] = mapped_column(
        SAEnum(WalletTransactionStatus, name="wallet_transaction_status"),
        default=WalletTransactionStatus.COMPLETED,
        nullable=False,
    )

    # =====================================================
    # FRAUD
    # =====================================================
    is_flagged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_wallet_tx_wallet", "wallet_id"),
        Index("idx_wallet_tx_reference", "reference_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<WalletTransaction(id={self.id}, "
            f"type={self.type}, amount={self.amount})>"
        )


# =========================================================
# WALLET PAYOUT
# =========================================================
class WalletPayout(Base):
    __tablename__ = "wallet_payouts"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =====================================================
    # RELATION
    # =====================================================
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    wallet = relationship(
        "Wallet",
        back_populates="payouts",
    )

    # =====================================================
    # MONEY
    # =====================================================
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # =====================================================
    # METHOD
    # =====================================================
    method: Mapped[WalletPayoutMethod] = mapped_column(
        SAEnum(WalletPayoutMethod, name="wallet_payout_method"),
        nullable=False,
    )

    # =====================================================
    # DESTINATION
    # =====================================================
    account_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    account_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    # =====================================================
    # STATUS
    # =====================================================
    status: Mapped[WalletPayoutStatus] = mapped_column(
        SAEnum(WalletPayoutStatus, name="wallet_payout_status"),
        default=WalletPayoutStatus.PENDING,
        nullable=False,
    )

    # =====================================================
    # ADMIN
    # =====================================================
    processed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    # =====================================================
    # SECURITY
    # =====================================================
    is_flagged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_wallet_payout_wallet", "wallet_id"),
    )


# =========================================================
# HOSPITAL BILLING
# =========================================================
class WalletBilling(Base):
    __tablename__ = "wallet_billings"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # =====================================================
    # TARGET
    # =====================================================
    hospital_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # =====================================================
    # MONEY
    # =====================================================
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    # =====================================================
    # BILLING TYPE
    # =====================================================
    type: Mapped[Optional[BillingType]] = mapped_column(
        SAEnum(BillingType, name="wallet_billing_type"),
        nullable=True,
    )

    reference_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # =====================================================
    # STATUS
    # =====================================================
    status: Mapped[BillingStatus] = mapped_column(
        SAEnum(BillingStatus, name="wallet_billing_status"),
        default=BillingStatus.PENDING,
        nullable=False,
    )

    # =====================================================
    # TIMESTAMPS
    # =====================================================
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("idx_wallet_billing_hospital", "hospital_id"),
    )