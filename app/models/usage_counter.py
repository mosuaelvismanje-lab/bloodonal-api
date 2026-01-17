from sqlalchemy import Column, String, Integer, UniqueConstraint
# ✅ REMOVED: from sqlalchemy.orm import declarative_base
# (Base is already defined in app.database, so we don't create a new one here)

from app.database import Base

class UsageCounter(Base):
    __tablename__ = "usage_counter"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(String, nullable=False, index=True)
    # ✅ service_type matches the "bike" / "doctor" strings we use in the Repository
    service_type = Column(String, nullable=False, index=True)

    used = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "service_type", name="uq_user_service"),
    )

    def __repr__(self):
        return f"<UsageCounter(user={self.user_id}, service={self.service_type}, used={self.used})>"
