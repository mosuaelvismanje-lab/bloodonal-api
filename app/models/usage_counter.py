from sqlalchemy import Column, String, Integer, UniqueConstraint
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class UsageCounter(Base):
    __tablename__ = "usage_counter"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(String, nullable=False)
    service_type = Column(String, nullable=False)

    used = Column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "service_type", name="uq_user_service"),
    )
