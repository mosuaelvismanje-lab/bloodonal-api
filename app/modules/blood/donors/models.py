from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    Index,
    Float,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base


class BloodDonor(Base):
    __tablename__ = "donors"

    # =========================================================
    # IDENTITY
    # =========================================================
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        unique=True,
    )

    # LINK TO AUTH USER
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        unique=True,
        index=True,
    )

    # =========================================================
    # BASIC PROFILE
    # =========================================================
    full_name = Column(
        String(150),
        nullable=False,
        index=True,
    )

    phone = Column(
        String(30),
        nullable=False,
        unique=True,
        index=True,
    )

    city = Column(
        String(100),
        nullable=False,
        index=True,
    )

    blood_group = Column(
        String(5),
        nullable=False,
        index=True,
    )

    # =========================================================
    # STATUS / AVAILABILITY
    # =========================================================
    is_available = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # DONOR CAN RECEIVE REQUESTS
    accepts_requests = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # VERIFIED BY HEALTHCARE SYSTEM
    is_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # =========================================================
    # LOCATION
    # =========================================================
    latitude = Column(
        Float,
        nullable=True,
    )

    longitude = Column(
        Float,
        nullable=True,
    )

    hospital_affiliation = Column(
        String(255),
        nullable=True,
    )

    # =========================================================
    # DONATION TRACKING
    # =========================================================
    last_donation_date = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    next_eligible_date = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    total_donations = Column(
        Integer,
        nullable=False,
        default=0,
    )

    completed_donations = Column(
        Integer,
        nullable=False,
        default=0,
    )

    cancelled_requests = Column(
        Integer,
        nullable=False,
        default=0,
    )

    successful_responses = Column(
        Integer,
        nullable=False,
        default=0,
    )

    rejection_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    active_matches = Column(
        Integer,
        nullable=False,
        default=0,
    )

    accepted_requests = Column(
        Integer,
        nullable=False,
        default=0,
    )

    total_lives_helped = Column(
        Integer,
        nullable=False,
        default=0,
    )

    donation_streak = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # =========================================================
    # REWARDS / GAMIFICATION
    # =========================================================
    points = Column(
        Integer,
        nullable=False,
        default=0,
    )

    rank_level = Column(
        String(20),
        nullable=False,
        default="Bronze",
        index=True,
    )

    success_rate = Column(
        Float,
        nullable=False,
        default=0.0,
    )

    # =========================================================
    # WALLET / REFERRAL
    # =========================================================
    wallet_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    referral_code = Column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
    )

    referred_by = Column(
        String(50),
        nullable=True,
        index=True,
    )

    referral_count = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # =========================================================
    # DEVICE / NOTIFICATIONS
    # =========================================================
    fcm_token = Column(
        String(255),
        nullable=True,
        index=True,
    )

    last_seen_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =========================================================
    # TIMESTAMPS
    # =========================================================
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # =========================================================
    # INDEXES
    # =========================================================
    __table_args__ = (
        Index(
            "ix_donors_city_blood_available",
            "city",
            "blood_group",
            "is_available",
        ),
        Index(
            "ix_donors_active_available",
            "is_active",
            "is_available",
        ),
        Index(
            "ix_donors_rank_points",
            "rank_level",
            "points",
        ),
        Index(
            "ix_donors_matching",
            "city",
            "blood_group",
            "is_active",
            "is_available",
        ),
        Index(
            "ix_donors_success",
            "success_rate",
            "completed_donations",
        ),
    )

    # =========================================================
    # HELPERS
    # =========================================================
    @property
    def can_donate(self) -> bool:
        return (
            self.is_active
            and self.is_available
            and self.accepts_requests
        )

    # =========================================================
    # DEBUG
    # =========================================================
    def __repr__(self):
        return (
            f"<BloodDonor("
            f"id={self.id}, "
            f"name={self.full_name}, "
            f"blood_group={self.blood_group}, "
            f"city={self.city}, "
            f"available={self.is_available}, "
            f"points={self.points}, "
            f"rank={self.rank_level}"
            f")>"
        )