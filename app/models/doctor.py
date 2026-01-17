from sqlalchemy import Column, String, Boolean
# ✅ REMOVED: from sqlalchemy.ext.declarative import declarative_base
# ✅ REMOVED: Base = declarative_base()

# ✅ ADDED: Use the central Base from your database config
# This ensures SQLAlchemy sees this model when you run migrations or init_db()
from app.database import Base

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    is_online = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Doctor(id={self.id}, name={self.name}, is_online={self.is_online})>"
