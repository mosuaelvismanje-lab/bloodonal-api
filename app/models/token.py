from sqlalchemy import Column, String, DateTime, func
from app.database import Base

class UserToken(Base):
    """
    Stores FCM registration tokens for users.
    Primary key is the token itself to allow a single user to have multiple devices.
    """
    __tablename__ = "user_tokens"

    # ✅ Token as primary key handles multi-device users naturally
    token = Column(String, primary_key=True)

    # ✅ Indexed for fast lookups when sending notifications to a specific user
    user_id = Column(String, index=True, nullable=False)

    # ✅ FIX: Use func.now() to match 'TIMESTAMP WITHOUT TIME ZONE' in Neon.
    # This prevents the 'offset-naive vs offset-aware' DataError.
    created_at = Column(DateTime, default=func.now(), server_default=func.now())

    def __repr__(self):
        return f"<UserToken(user_id={self.user_id}, token={self.token[:10]}...)>"