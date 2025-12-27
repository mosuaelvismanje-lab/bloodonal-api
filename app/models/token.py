# app/models/token.py

from sqlalchemy import Column, String
from app.database import Base


class UserToken(Base):
    __tablename__ = "user_tokens"

    user_id = Column(String, primary_key=True, index=True)
    token = Column(String, nullable=False)
