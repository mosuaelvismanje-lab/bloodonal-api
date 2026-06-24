from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base
from app.modules.blood.domain.enum import BloodRequestStatusEnum


# =========================================================
# BLOOD REQUEST MODEL
# =========================================================
class BloodRequest(Base):
    __tablename__ = "blood_requests"

    # =====================================================
    # PRIMARY KEY
    # =====================================================
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        unique=True,
    )

    # =====================================================
    # PATIENT INFO
    # =====================================================
    patient_name = Column(String(150), nullable=False, index=True)
    phone = Column(String(30), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)

    # =====================================================
    # MEDICAL INFO
    # =====================================================
    blood_group = Column(String(5), nullable=False, index=True)

    hospital_location = Column(
        String(255),
        nullable=False,
    )

    needed_units = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    # =====================================================
    # URGENCY
    # =====================================================
    # 1 = Normal
    # 2 = Moderate
    # 3 = High
    # 4 = Critical / Emergency
    urgency_level = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
        index=True,
    )

    # Legacy compatibility field.
    # Can be removed later after frontend migration.
    is_urgent = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    # =====================================================
    # BUSINESS
    # =====================================================
    offer = Column(
        String(255),
        nullable=False,
        default="Voluntary",
        server_default=text("'Voluntary'"),
    )

    incentive_amount = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    # =====================================================
    # OWNERSHIP
    # =====================================================
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # =====================================================
    # DONOR LINK
    # =====================================================
    accepted_by = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "donors.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =====================================================
    # STATUS
    # =====================================================
    status = Column(
        Enum(
            BloodRequestStatusEnum,
            name="blood_request_status",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        default=BloodRequestStatusEnum.ACTIVE,
        server_default=text("'ACTIVE'"),
        index=True,
    )

    # =====================================================
    # TIMELINE
    # =====================================================
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # ANALYTICS
    # =====================================================
    total_matches_sent = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    total_views = Column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    # =====================================================
    # SOFT DELETE
    # =====================================================
    is_deleted = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # =====================================================
    # OPTIMISTIC LOCKING
    # =====================================================
    version = Column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    __mapper_args__ = {
        "version_id_col": version,
    }

    # =====================================================
    # INDEXES + CONSTRAINTS
    # =====================================================
    __table_args__ = (
        Index("idx_req_city_status", "city", "status"),
        Index("idx_req_group_status", "blood_group", "status"),
        Index("idx_req_user_status", "user_id", "status"),
        Index("idx_req_created", "created_at"),
        Index("idx_req_accept_flow", "accepted_by", "status"),
        Index(
            "idx_req_match",
            "city",
            "blood_group",
            "status",
            "expires_at",
        ),
        Index(
            "idx_req_active",
            "status",
            "is_deleted",
            "expires_at",
        ),
        Index(
            "idx_req_urgency",
            "urgency_level",
            "status",
            "expires_at",
        ),

        # =================================================
        # BUSINESS RULES
        # =================================================
        CheckConstraint(
            "needed_units > 0",
            name="ck_units_positive",
        ),

        CheckConstraint(
            "total_matches_sent >= 0",
            name="ck_matches_non_negative",
        ),

        CheckConstraint(
            "total_views >= 0",
            name="ck_views_non_negative",
        ),

        CheckConstraint(
            "version >= 1",
            name="ck_version_positive",
        ),

        CheckConstraint(
            "expires_at > created_at",
            name="ck_expiry_valid",
        ),

        CheckConstraint(
            "urgency_level >= 1 AND urgency_level <= 4",
            name="ck_urgency_range",
        ),

        CheckConstraint(
            "(is_deleted = false AND deleted_at IS NULL) "
            "OR "
            "(is_deleted = true AND deleted_at IS NOT NULL)",
            name="ck_soft_delete_consistency",
        ),

        CheckConstraint(
            "("
            "status = 'ACTIVE' "
            "AND accepted_by IS NULL "
            "AND accepted_at IS NULL "
            "AND completed_at IS NULL"
            ") OR ("
            "status = 'ACCEPTED' "
            "AND accepted_by IS NOT NULL "
            "AND accepted_at IS NOT NULL "
            "AND completed_at IS NULL"
            ") OR ("
            "status = 'COMPLETED' "
            "AND accepted_by IS NOT NULL "
            "AND accepted_at IS NOT NULL "
            "AND completed_at IS NOT NULL"
            ") OR ("
            "status IN ('CANCELLED', 'EXPIRED')"
            ")",
            name="ck_lifecycle_consistency",
        ),
    )

    # =====================================================
    # DEBUG
    # =====================================================
    def __repr__(self) -> str:
        return (
            f"<BloodRequest "
            f"id={self.id} "
            f"status={self.status} "
            f"city={self.city} "
            f"blood_group={self.blood_group} "
            f"urgency_level={self.urgency_level}>"
        )