# app/database.py
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# === Database Engine ===
try:
    # --- TEMPORARY DEBUG CODE (Check the URL value) ---
    url_to_use = settings.ASYNC_DATABASE_URL
    print("\n--- DB URL DEBUG START ---")
    print(f"URL Starts With: '{url_to_use.strip()[:30]}'")
    print(f"URL Length: {len(url_to_use.strip())}")
    print("--- DB URL DEBUG END ---\n")
    # --------------------------------------------------

    engine = create_async_engine(
        # FIX: Use .strip() to clean the URL string from hidden whitespace/newlines
        url_to_use.strip(),
        echo=settings.DEBUG,
        pool_pre_ping=True,
        future=True,
        # pool_size / max_overflow ignored by async engines, you can remove or leave
    )
    logger.info("Async SQLAlchemy engine initialized")
except Exception as exc:
    logger.exception("Failed to initialize async SQLAlchemy engine: %s", exc)
    raise

# ---

# === Session Factory ===
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# === Base Class for Models ===
Base = declarative_base()

# ---

# === Dependency for FastAPI Routes ===
async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as exc:
            logger.exception("DB session error: %s", exc)
            raise
        finally:
            await session.close()

# ---

# === DB Initialization (Development Only) ===
async def init_db() -> None:
    """
    ⚠️ Development only. In production, run Alembic migrations instead.
    """
    import app.models  # noqa: F401 ensures models are imported
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully (development only).")
    except Exception as exc:
        logger.exception("Failed to initialize database: %s", exc)
        raise