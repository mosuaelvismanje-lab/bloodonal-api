# app/database.py
from __future__ import annotations

from typing import AsyncIterator, Generator, Optional
import logging

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# =====================================================================
# Declarative Base
# =====================================================================
Base = declarative_base()

# =====================================================================
# ASYNC Engine (FastAPI)
# =====================================================================
try:
    ASYNC_DATABASE_URL = settings.ASYNC_DATABASE_URL
except Exception as exc:  # pragma: no cover
    logger.exception("Missing or invalid ASYNC_DATABASE_URL in settings: %s", exc)
    raise

if settings.DEBUG:
    prefix = ASYNC_DATABASE_URL[:40]
    logger.info("Initializing async engine, url startswith=%s (len=%d)", prefix, len(ASYNC_DATABASE_URL))

async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

logger.info("✅ Async engine initialized (for FastAPI)")


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as exc:
            logger.exception("⚠️ DB session error (async): %s", exc)
            raise
        finally:
            await session.close()


# =====================================================================
# SYNC Engine (Alembic / Scripts)
# =====================================================================
SYNC_DATABASE_URL: Optional[str] = None
try:
    SYNC_DATABASE_URL = settings.SYNC_DATABASE_URL
except Exception:
    SYNC_DATABASE_URL = None

sync_engine: Optional[Engine] = None
SyncSessionLocal: Optional[sessionmaker] = None

if SYNC_DATABASE_URL:
    try:
        if settings.DEBUG:
            prefix = SYNC_DATABASE_URL[:40]
            logger.info("Initializing sync engine, url startswith=%s (len=%d)", prefix, len(SYNC_DATABASE_URL))
        sync_engine = create_engine(
            SYNC_DATABASE_URL,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
        )
        SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, future=True)
        logger.info("✅ Sync engine initialized (for Alembic / scripts)")
    except Exception as exc:
        logger.exception("❌ Failed to initialize sync SQLAlchemy engine: %s", exc)
else:
    logger.warning("Sync DATABASE_URL not configured; Alembic may not work.")


@contextmanager
def get_sync_session() -> Generator:
    """Context manager for synchronous DB sessions."""
    if SyncSessionLocal is None:
        raise RuntimeError("Sync session factory not configured.")

    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# =====================================================================
# Shutdown helpers
# =====================================================================
async def dispose_async_engine() -> None:
    try:
        await async_engine.dispose()
        logger.info("Async engine disposed")
    except Exception as exc:
        logger.exception("Error disposing async engine: %s", exc)


def dispose_sync_engine() -> None:
    try:
        if sync_engine:
            sync_engine.dispose()
            logger.info("Sync engine disposed")
    except Exception as exc:
        logger.exception("Error disposing sync engine: %s", exc)


# =====================================================================
# Development helper: Create tables
# =====================================================================
async def init_db() -> None:
    """Development helper — creates tables using SQLAlchemy metadata."""
    import app.models  # noqa: F401

    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully.")
    except Exception as exc:
        logger.exception("❌ Failed to initialize database (init_db): %s", exc)
        raise


# =====================================================================
# Free Usage Helpers (REQUIRED BY payment_service.py)
# =====================================================================

async def get_free_usage_count(db: AsyncSession, user_id: str, category: str) -> int:
    """
    Returns how many free usages a user has consumed.
    """
    result = await db.scalar(
        text("""
            SELECT count 
            FROM free_usage 
            WHERE user_id = :user_id AND category = :category
        """),
        {"user_id": user_id, "category": category}
    )
    return result or 0


async def increment_usage_count(db: AsyncSession, user_id: str, category: str) -> None:
    """
    Increments the usage counter for free quota.
    Creates the row if it does not exist.
    """
    await db.execute(
        text("""
            INSERT INTO free_usage (user_id, category, count)
            VALUES (:user_id, :category, 1)
            ON CONFLICT (user_id, category)
            DO UPDATE SET count = free_usage.count + 1
        """),
        {"user_id": user_id, "category": category}
    )
