
# app/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.database import get_async_session

async def get_db(session: AsyncSession = Depends(get_async_session)):
    return session
