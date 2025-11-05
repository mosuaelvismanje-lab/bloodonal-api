# app/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.database import get_async_session

async def get_db() -> AsyncSession:
    """
    Async dependency to provide an AsyncSession for FastAPI endpoints.
    """
    async with get_async_session() as session:
        yield session
