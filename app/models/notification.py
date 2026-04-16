import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Notification(Base):
    __tablename__ = "notifications"

    # ✅ UUID Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ✅ recipient user ID or Topic Name (e.g., "donation")
    user_id = Column(String, index=True, nullable=False)

    # ✅ Optional title
    title = Column(String, nullable=True)

    # ✅ E.g., "generic", "alert", "blood_request"
    sub_type = Column(String, nullable=False, default="generic")

    # ✅ Changed to nullable=True to support broadcasts
    location = Column(String, nullable=True, default="N/A")
    phone = Column(String, nullable=True, default="N/A")

    # ✅ The main message body
    message = Column(String, nullable=False)

    # ✅ Epoch milliseconds (standard for Flutter/Mobile synchronization)
    timestamp = Column(BigInteger, nullable=False)

    # ✅ Unread by default
    read = Column(Boolean, default=False, nullable=False)

    # ✅ FIXED: Stripping tzinfo to prevent 'offset-naive and offset-aware' crash
    # PostgreSQL 'TIMESTAMP WITHOUT TIME ZONE' requires naive datetime objects.
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False
    )

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, user_id={self.user_id}, "
            f"title={self.title}, sub_type={self.sub_type}, read={self.read})>"
        )