from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import AsyncIterator, Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

logger = logging.getLogger("uvicorn.error")

# =====================================================================
# Declarative Base
# =====================================================================
Base = declarative_base()


# =====================================================================
# Helper: URL Sanitization
# =====================================================================
def get_cleaned_url(url: str, is_async: bool = True) -> str:
    """Strips query params like sslmode that crash specific drivers."""
    if not url:
        return url

    # Remove everything after '?' to prevent driver argument conflicts
    clean_url = url.split("?")[0]

    if is_async and clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return clean_url


# =====================================================================
# ASYNC Engine (FastAPI)
# =====================================================================
try:
    ASYNC_DATABASE_URL = get_cleaned_url(settings.ASYNC_DATABASE_URL, is_async=True)
except Exception as exc:
    logger.exception("Missing or invalid ASYNC_DATABASE_URL in settings: %s", exc)
    raise

# Define SSL requirements for Async (asyncpg uses 'ssl')
async_connect_args = {}
if "neon.tech" in ASYNC_DATABASE_URL or not settings.DEBUG:
    async_connect_args = {"ssl": "require"}

async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

logger.info("✅ Async engine initialized (Standardized)")


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Primary FastAPI dependency for async sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as exc:
            logger.exception("⚠️ DB session error (async): %s", exc)
            raise
        finally:
            await session.close()


# Alias for code using 'get_db'
get_db = get_async_session


# =====================================================================
# SYNC Engine (Alembic / Scripts)
# =====================================================================
SYNC_DATABASE_URL: Optional[str] = None
try:
    SYNC_DATABASE_URL = get_cleaned_url(settings.SYNC_DATABASE_URL, is_async=False)
except Exception:
    SYNC_DATABASE_URL = None

sync_engine: Optional[Engine] = None
SyncSessionLocal: Optional[sessionmaker] = None

if SYNC_DATABASE_URL:
    try:
        # Sync driver (psycopg2) uses 'sslmode'
        sync_connect_args = {}
        if "neon.tech" in SYNC_DATABASE_URL or not settings.DEBUG:
            sync_connect_args = {"sslmode": "require"}

        sync_engine = create_engine(
            SYNC_DATABASE_URL,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
            connect_args=sync_connect_args,
        )
        SyncSessionLocal = sessionmaker(
            bind=sync_engine, expire_on_commit=False, future=True
        )
        logger.info("✅ Sync engine initialized (Standardized)")
    except Exception as exc:
        logger.exception("❌ Failed to initialize sync SQLAlchemy engine: %s", exc)
else:
    logger.warning("Sync DATABASE_URL not configured.")


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
# Lifecycle & Helper Methods
# =====================================================================
async def dispose_async_engine() -> None:
    await async_engine.dispose()


def dispose_sync_engine() -> None:
    if sync_engine:
        sync_engine.dispose()


async def init_db() -> None:
    """Creates tables using SQLAlchemy metadata."""
    import app.models  # noqa: F401
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_free_usage_count(db: AsyncSession, user_id: str, category: str) -> int:
    result = await db.scalar(
        text(
            "SELECT count FROM free_usage WHERE user_id = :user_id AND category = :category"
        ),
        {"user_id": user_id, "category": category},
    )
    return result or 0


async def increment_usage_count(db: AsyncSession, user_id: str, category: str) -> None:
    await db.execute(
        text(
            """
            INSERT INTO free_usage (user_id, category, count)
            VALUES (:user_id, :category, 1)
            ON CONFLICT (user_id, category)
            DO UPDATE SET count = free_usage.count + 1
        """
        ),
        {"user_id": user_id, "category": category},
    )
    await db.commit()