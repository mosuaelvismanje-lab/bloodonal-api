from __future__ import annotations

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncIterator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

logger = logging.getLogger("bloodonal.database")

# ==========================================================
# BASE
# ==========================================================

Base = declarative_base()

# ==========================================================
# URL HELPERS
# ==========================================================


def normalize_database_url(
    url: str | None,
    *,
    async_driver: bool,
) -> str:
    """
    Normalize PostgreSQL URLs.

    Removes query parameters because
    SQLAlchemy connect_args handles SSL.
    """

    if not url:
        return "postgresql://postgres:postgres@localhost:5432/bloodonal"

    url = url.split("?")[0]

    if async_driver and url.startswith("postgresql://"):
        url = url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )

    return url


ASYNC_DATABASE_URL = normalize_database_url(
    settings.ASYNC_DATABASE_URL,
    async_driver=True,
)

SYNC_DATABASE_URL = normalize_database_url(
    settings.DATABASE_URL,
    async_driver=False,
)

# ==========================================================
# LOG DATABASE HOST
# ==========================================================

logger.info(
    "Database configured (%s)",
    ASYNC_DATABASE_URL.split("@")[-1],
)

# ==========================================================
# ASYNC ENGINE
# ==========================================================

async_connect_args: dict[str, object] = {
    "ssl": "require",
    "timeout": 120,
    "command_timeout": 120,
    "prepared_statement_cache_size": 0,
    "server_settings": {
        "jit": "off",
        "application_name": "bloodonal_api_async",
    },
}

async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,

    # IMPORTANT FOR NEON
    poolclass=NullPool,

    pool_pre_ping=True,

    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ==========================================================
# ASYNC SESSION
# ==========================================================


async def get_async_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session

        except SQLAlchemyError:
            logger.exception(
                "Database async session error"
            )
            await session.rollback()
            raise

        finally:
            await session.close()


get_db = get_async_session

# ==========================================================
# SYNC ENGINE
# ==========================================================

sync_engine = create_engine(
    SYNC_DATABASE_URL,

    # IMPORTANT FOR NEON
    poolclass=NullPool,

    connect_args={
        "sslmode": "require",
        "connect_timeout": 120,
        "application_name": "bloodonal_api_sync",
    },

    pool_pre_ping=True,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)

# ==========================================================
# SYNC SESSION
# ==========================================================


@contextmanager
def get_sync_session() -> Generator:
    session = SyncSessionLocal()

    try:
        yield session
        session.commit()

    except Exception:
        session.rollback()

        logger.exception(
            "Database sync session error"
        )

        raise

    finally:
        session.close()


# ==========================================================
# DATABASE STARTUP
# ==========================================================


async def init_db() -> None:
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        logger.info(
            "✅ Database tables initialized"
        )

    except Exception:
        logger.exception(
            "❌ Failed to initialize database"
        )
        raise


# ==========================================================
# DATABASE HEALTH CHECK
# ==========================================================


async def check_database_connection() -> bool:
    try:
        async with async_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT 1")
            )

            result.scalar()

        return True

    except Exception:
        logger.exception(
            "Database health check failed"
        )

        return False


# ==========================================================
# SHUTDOWN
# ==========================================================


async def close_database() -> None:
    try:
        await async_engine.dispose()

        logger.info(
            "✅ Database connections closed"
        )

    except Exception:
        logger.exception(
            "Failed closing database"
        )