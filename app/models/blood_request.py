from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from app.database import Base


class BloodRequest(Base):
    """
    SQLAlchemy model representing a blood donation request in Neon Postgres.
    Modular Update: Optimized for status-based queries and background janitor tasks.
    """
    __tablename__ = "blood_requests"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ Ownership: Links the request to the Firebase UID
    user_id = Column(String, index=True, nullable=False)

    # Requester Details
    requester_name = Column(String(100), nullable=False)
    city = Column(String(50), nullable=False, index=True)
    phone = Column(String(20), nullable=False)

    # Medical Requirements
    blood_type = Column(String(5), nullable=False, index=True)
    needed_units = Column(Integer, default=1, nullable=False)
    hospital = Column(String(150), nullable=True)
    urgent = Column(Boolean, default=True)

    # ✅ Request Lifecycle Management
    # Standard Statuses: PENDING, FULFILLED, EXPIRED, CANCELLED
    status = Column(String(20), default="PENDING", nullable=False, index=True)

    # ✅ Timestamps: Crucial for Janitor tasks and UI sorting
    # Added index=True to created_at to speed up "find expired" queries
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True
    )

    # server_default ensures it's not null at creation;
    # onupdate handles the automatic timestamp shift when status changes
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )