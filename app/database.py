# app/database.py
from __future__ import annotations

from typing import AsyncIterator, Generator, Optional
import logging

from contextlib import contextmanager

from sqlalchemy import create_engine
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

# -------------------------
# Declarative base (export for Alembic/autogenerate)
# -------------------------
Base = declarative_base()

# -------------------------
# ASYNC Engine (FastAPI / asyncpg)
# -------------------------
# Expect settings.ASYNC_DATABASE_URL to be present and properly formed.
try:
    ASYNC_DATABASE_URL = settings.ASYNC_DATABASE_URL
except Exception as exc:  # pragma: no cover - configuration errors
    logger.exception("Missing or invalid ASYNC_DATABASE_URL in settings: %s", exc)
    raise

# small masked debug output (do not print full URL or credentials)
if settings.DEBUG:
    prefix = ASYNC_DATABASE_URL[:40].replace(":", ":")  # avoid accidental transformations
    logger.info("Initializing async engine, url startswith=%s (len=%d)", prefix, len(ASYNC_DATABASE_URL))

async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

logger.info("✅ Async engine initialized (for FastAPI)")

# Async dependency for FastAPI
async def get_async_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency: yields an AsyncSession.
    Usage:
        async def route(db: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as exc:
            logger.exception("⚠️ DB session error (async): %s", exc)
            raise
        finally:
            # session will be closed automatically by contextmanager, but ensure close for safety
            await session.close()


# -------------------------
# SYNC Engine (Alembic / scripts)
# -------------------------
# settings.SYNC_DATABASE_URL should convert/derive a sync URL (psycopg2) for Alembic.
SYNC_DATABASE_URL: Optional[str] = None
try:
    SYNC_DATABASE_URL = settings.SYNC_DATABASE_URL
except Exception:
    # It's acceptable for sync URL to be missing in strictly async-only environments.
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
        sync_engine = None
        SyncSessionLocal = None
else:
    logger.warning(
        "Sync DATABASE_URL not configured; Alembic or sync scripts may not work until SYNC_DATABASE_URL is set."
    )


@contextmanager
def get_sync_session() -> Generator:
    """
    Context manager for synchronous DB sessions (scripts / CLI / Alembic helpers).
    Usage:
        with get_sync_session() as session:
            session.execute(...)
    """
    if SyncSessionLocal is None:
        raise RuntimeError("Sync session factory not configured (DATABASE_URL / SYNC_DATABASE_URL missing)")
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# -------------------------
# Shutdown helpers
# -------------------------
async def dispose_async_engine() -> None:
    """Dispose the async engine (useful on shutdown in some hosting environments)."""
    try:
        await async_engine.dispose()
        logger.info("Async engine disposed")
    except Exception as exc:
        logger.exception("Error disposing async engine: %s", exc)


def dispose_sync_engine() -> None:
    """Dispose the sync engine if present."""
    try:
        if sync_engine:
            sync_engine.dispose()
            logger.info("Sync engine disposed")
    except Exception as exc:
        logger.exception("Error disposing sync engine: %s", exc)


# -------------------------
# Development helper: create tables (async)
# -------------------------
async def init_db() -> None:
    """
    Development helper — creates tables using metadata.
    In production use Alembic migrations instead.
    """
    # ensure models are imported so metadata is populated
    import app.models  # noqa: F401

    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully (development only).")
    except Exception as exc:
        logger.exception("❌ Failed to initialize database (init_db): %s", exc)
        raise
