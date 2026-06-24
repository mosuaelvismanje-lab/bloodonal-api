# G:\pycharm\bloodonal-api\app\modules\rewards\user.py

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


# =========================================================
# CONSTANTS
# =========================================================
DEFAULT_CURRENCY_PRECISION = (18, 2)

REWARD_STATUS_PENDING = "pending"
REWARD_STATUS_SUCCESS = "success"
REWARD_STATUS_FAILED = "failed"
REWARD_STATUS_BLOCKED = "blocked"

VALID_REWARD_STATUSES = (
    REWARD_STATUS_PENDING,
    REWARD_STATUS_SUCCESS,
    REWARD_STATUS_FAILED,
    REWARD_STATUS_BLOCKED,
)


# =========================================================
# COMMON MIXINS
# =========================================================
class TimestampMixin:
    """
    Shared audit timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# =========================================================
# 🎯 REWARD TRANSACTION MODEL
# =========================================================
class RewardTransaction(Base, TimestampMixin):
    """
    Immutable reward transaction ledger.

    Enterprise Guarantees
    ---------------------------------------------------
    ✔ audit traceability
    ✔ idempotency-safe references
    ✔ fraud analytics ready
    ✔ payout reconciliation
    ✔ SQLAlchemy 2.0 typed model
    ✔ async-safe
    ✔ reporting optimized
    """

    __tablename__ = "reward_transactions"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # =====================================================
    # OWNERSHIP
    # =====================================================
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    wallet_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "wallets.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =====================================================
    # BUSINESS REFERENCES
    # =====================================================
    reference: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
    )

    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    reason: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        default="BLOOD_DONATION_REWARD",
    )

    # =====================================================
    # FINANCIALS
    # =====================================================
    reward_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    wallet_credit: Mapped[Decimal] = mapped_column(
        Numeric(*DEFAULT_CURRENCY_PRECISION),
        nullable=False,
        default=Decimal("0.00"),
    )

    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(*DEFAULT_CURRENCY_PRECISION),
        nullable=False,
        default=Decimal("0.00"),
    )

    # =====================================================
    # REWARD ENGINE OUTPUT
    # =====================================================
    reward_label: Mapped[Optional[str]] = mapped_column(
        String(80),
        nullable=True,
    )

    surge_multiplier: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )

    # =====================================================
    # FRAUD + SECURITY
    # =====================================================
    risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    fraud_flags: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    is_fraud_blocked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # =====================================================
    # STATUS
    # =====================================================
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=REWARD_STATUS_PENDING,
        index=True,
    )

    message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # =====================================================
    # CONTEXT SNAPSHOT
    # =====================================================
    reward_context: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    worker_meta: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # =====================================================
    # GAMIFICATION
    # =====================================================
    donor_rank: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    streak_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    badges_awarded: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # =====================================================
    # REFERRALS
    # =====================================================
    referral_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    referral_bonus_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    referred_user_id: Mapped[Optional[UUID]] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # =====================================================
    # PROCESSING
    # =====================================================
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # AUDIT
    # =====================================================
    audit_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    audit_source: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    # =====================================================
    # CONSTRAINTS
    # =====================================================
    __table_args__ = (
        UniqueConstraint(
            "reference",
            name="uq_reward_transactions_reference",
        ),

        CheckConstraint(
            "reward_points >= 0",
            name="ck_reward_points_non_negative",
        ),

        CheckConstraint(
            "wallet_credit >= 0",
            name="ck_wallet_credit_non_negative",
        ),

        CheckConstraint(
            "base_amount >= 0",
            name="ck_base_amount_non_negative",
        ),

        CheckConstraint(
            "surge_multiplier >= 1.0",
            name="ck_surge_multiplier_positive",
        ),

        CheckConstraint(
            "risk_score >= 0",
            name="ck_risk_score_non_negative",
        ),

        CheckConstraint(
            f"status IN {VALID_REWARD_STATUSES}",
            name="ck_reward_status_valid",
        ),

        Index(
            "ix_reward_user_status",
            "user_id",
            "status",
        ),

        Index(
            "ix_reward_wallet_created",
            "wallet_id",
            "created_at",
        ),

        Index(
            "ix_reward_reference_status",
            "reference",
            "status",
        ),

        Index(
            "ix_reward_processed_at",
            "processed_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"RewardTransaction("
            f"id={self.id}, "
            f"user_id={self.user_id}, "
            f"status={self.status}, "
            f"points={self.reward_points}"
            f")"
        )


# =========================================================
# 🎖️ DONOR REWARD PROFILE
# =========================================================
class DonorRewardProfile(Base, TimestampMixin):
    """
    Persistent donor reward profile.

    Stores:
    ---------------------------------------------
    ✔ donor rank
    ✔ streak metrics
    ✔ referrals
    ✔ badges
    ✔ accelerated dashboard stats
    """

    __tablename__ = "donor_reward_profiles"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    donor_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )

    total_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_rewards: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_wallet_credit: Mapped[Decimal] = mapped_column(
        Numeric(*DEFAULT_CURRENCY_PRECISION),
        nullable=False,
        default=Decimal("0.00"),
    )

    current_rank: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Bronze",
    )

    next_rank: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    next_rank_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    streak_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    highest_streak: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    badges: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    referral_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
    )

    total_referrals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    successful_referrals: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    referral_bonus_points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # =====================================================
    # CONSTRAINTS
    # =====================================================
    __table_args__ = (
        CheckConstraint(
            "total_points >= 0",
            name="ck_profile_total_points_non_negative",
        ),

        CheckConstraint(
            "total_rewards >= 0",
            name="ck_profile_total_rewards_non_negative",
        ),

        CheckConstraint(
            "streak_count >= 0",
            name="ck_profile_streak_non_negative",
        ),

        CheckConstraint(
            "highest_streak >= 0",
            name="ck_profile_highest_streak_non_negative",
        ),

        CheckConstraint(
            "total_referrals >= 0",
            name="ck_profile_total_referrals_non_negative",
        ),

        CheckConstraint(
            "successful_referrals >= 0",
            name="ck_profile_successful_referrals_non_negative",
        ),

        Index(
            "ix_profile_rank_points",
            "current_rank",
            "total_points",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"DonorRewardProfile("
            f"donor_id={self.donor_id}, "
            f"rank={self.current_rank}, "
            f"points={self.total_points}"
            f")"
        )


# =========================================================
# 🎁 REWARD CATALOG
# =========================================================
class RewardCatalog(Base, TimestampMixin):
    """
    Redeemable reward catalog.

    Examples:
    -------------------------------------
    - Airtime
    - Hospital vouchers
    - Gift cards
    - Transport support
    """

    __tablename__ = "reward_catalog"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
        index=True,
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    points_required: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    reward_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="voucher",
        index=True,
    )

    reward_value: Mapped[Decimal] = mapped_column(
        Numeric(*DEFAULT_CURRENCY_PRECISION),
        nullable=False,
        default=Decimal("0.00"),
    )

    stock_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "points_required >= 0",
            name="ck_catalog_points_required_non_negative",
        ),

        CheckConstraint(
            "reward_value >= 0",
            name="ck_catalog_reward_value_non_negative",
        ),

        CheckConstraint(
            "stock_quantity >= 0",
            name="ck_catalog_stock_non_negative",
        ),

        Index(
            "ix_catalog_active_points",
            "is_active",
            "points_required",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"RewardCatalog("
            f"title={self.title}, "
            f"points_required={self.points_required}, "
            f"active={self.is_active}"
            f")"
        )