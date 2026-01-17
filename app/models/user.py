from sqlalchemy import Column, String, Boolean
# ✅ REMOVED: from sqlalchemy.orm import declarative_base
# ✅ REMOVED: Base = declarative_base()

# ✅ ADDED: Import the central Base from your database config
# This ensures User is included in migrations and init_db()
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)  # Firebase UID
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"
