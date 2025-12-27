# File: app/models/doctor.py
from sqlalchemy import Column, String, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    is_online = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Doctor(id={self.id}, name={self.name}, is_online={self.is_online})>"
