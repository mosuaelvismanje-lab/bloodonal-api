# app/database.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# === Database Engine ===
engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True
)

# === Session Factory ===
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# === Base Class for Models ===
Base = declarative_base()

# === Dependency for FastAPI Routes ===
async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# === DB Initialization (Development Only) ===
async def init_db() -> None:
    """
    ⚠️ Development only. In production, run Alembic migrations instead.
    """
    import app.models  # noqa: F401 ensures models are imported
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
