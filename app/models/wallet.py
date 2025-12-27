from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Wallet(Base):
    __tablename__ = "wallets"

    # One wallet per user (phone-based for USSD systems)
    user_phone = Column(String, primary_key=True, index=True)

    # Balance stored in smallest unit (XAF)
    balance = Column(Integer, nullable=False, default=0)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
