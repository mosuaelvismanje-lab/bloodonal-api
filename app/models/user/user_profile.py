# =========================================================
# FILE: app/models/user_profile.py
# =========================================================

from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Float,
    ForeignKey,
    Integer,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class UserProfile(Base):
    """
    =========================================================
    USER PROFILE (ENTERPRISE + HEALTHCARE READY)
    =========================================================
    """

    __tablename__ = "user_profiles"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # =====================================================
    # RELATION
    # =====================================================
    user_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.uid"),
        unique=True,
        index=True,
        nullable=False,
    )

    # =====================================================
    # BASIC PROFILE (MISSING BEFORE → NOW ADDED)
    # =====================================================
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(30), nullable=True)

    avatar_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    cover_photo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # =====================================================
    # LOCATION (NOW MATCHES FRONTEND + SERVICE)
    # =====================================================
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    state: Mapped[str | None] = mapped_column(String(120), nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # =====================================================
    # BLOOD & DONOR INFO
    # =====================================================
    blood_group: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        index=True,
    )

    is_donor: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )

    donation_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )

    last_donation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # MEDICAL INFO
    # =====================================================
    medical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    chronic_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # =====================================================
    # EMERGENCY CONTACT
    # =====================================================
    emergency_contact: Mapped[str | None] = mapped_column(String(50), nullable=True)
    emergency_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_relationship: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # =====================================================
    # TRUST SYSTEM
    # =====================================================
    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0")
    total_reviews: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # =====================================================
    # AUDIT (FIXED)
    # =====================================================
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # STATUS
    # =====================================================
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id}, blood_group={self.blood_group})>"