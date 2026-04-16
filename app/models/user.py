from sqlalchemy import Column, String, Boolean, DateTime, func
# ✅ Centralized Base imported correctly
from app.database import Base


class User(Base):
    """
    User model integrated with Firebase Authentication.
    Uses Firebase UID as the primary key.
    """
    __tablename__ = "users"

    # Firebase UID (e.g., 'vN8qB...')
    id = Column(String, primary_key=True, index=True)

    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)

    # Status and Permissions
    is_active = Column(Boolean, default=True, server_default="true")

    # Audit Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"