from typing import AsyncIterator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging
import os

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# =========================
# Database Engine
# =========================
try:
    # Prefer async DB URL from settings
    url_to_use: str | None = settings.ASYNC_DATABASE_URL or os.getenv("ASYNC_DATABASE_URL")

    # Fallback to sync URL and convert to async
    if not url_to_use:
        url_to_use = settings.DATABASE_URL or os.getenv("DATABASE_URL")
        if url_to_use and url_to_use.startswith("postgresql://"):
            url_to_use = url_to_use.replace("postgresql://", "postgresql+asyncpg://", 1)

    if not url_to_use:
        raise RuntimeError("No ASYNC_DATABASE_URL or DATABASE_URL found in environment")

    # --- Debugging Info ---
    if settings.DEBUG:
        print("\n--- DB URL DEBUG START ---")
        print(f"URL Starts With: '{url_to_use.strip()[:40]}'")
        print(f"URL Length: {len(url_to_use.strip())}")
        print("--- DB URL DEBUG END ---\n")

    # Create async engine
    engine = create_async_engine(
        url_to_use.strip(),
        echo=settings.DEBUG,
        pool_pre_ping=True,
        future=True,
    )
    logger.info("✅ Async SQLAlchemy engine initialized")

except Exception as exc:
    logger.exception("❌ Failed to initialize async SQLAlchemy engine: %s", exc)
    raise

# =========================
# Session Factory
# =========================
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# =========================
# Base Model
# =========================
Base = declarative_base()

# =========================
# FastAPI Dependency
# =========================
async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as exc:
            logger.exception("⚠️ DB session error: %s", exc)
            raise
        finally:
            await session.close()


# =========================
# Development DB Init
# =========================
async def init_db() -> None:
    """
    ⚠️ Development only: creates tables. In production, use Alembic migrations.
    """
    import app.models  # noqa: F401 ensures models are loaded
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully (development only).")
    except Exception as exc:
        logger.exception("❌ Failed to initialize database: %s", exc)
        raise
