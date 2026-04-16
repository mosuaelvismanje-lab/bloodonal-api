from sqlalchemy import Column, String, Integer, UniqueConstraint, DateTime, func
from app.database import Base

class UsageCounter(Base):
    """
    Tracks service usage, free quotas, and idempotency for a specific user.
    Standardized to match IUsageRepository interface and SQLAlchemyUsageRepository.
    """
    __tablename__ = "usage_counter"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 1. User Identity (e.g., test_user_99)
    user_id = Column(String, nullable=False, index=True)

    # 2. Standardized Service Name (Matches 'service' arg in Repository)
    service = Column(String, nullable=False, index=True)

    # 3. Usage Count
    # server_default ensures the DB handles the 0 initialization for atomic safety
    used = Column(Integer, server_default="0", default=0, nullable=False)

    # --- IDEMPOTENCY FIELDS ---

    # 4. Idempotency Key: Unique key to prevent duplicate processing
    # Added index=True to speed up get_by_idempotency_key lookups
    idempotency_key = Column(String, unique=True, nullable=True, index=True)

    # 5. Request ID: Stores the Room ID or Session ID (e.g., Agora channel name)
    request_id = Column(String, nullable=True)

    # --- AUDIT FIELDS ---
    # Tracks when the first and most recent usage happened
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    __table_args__ = (
        # Required for the Repository's .on_conflict_do_update() logic
        UniqueConstraint("user_id", "service", name="uq_user_service"),
    )

    def __repr__(self):
        return f"<UsageCounter(user={self.user_id}, service={self.service}, used={self.used})>"