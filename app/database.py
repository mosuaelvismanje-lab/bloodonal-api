# app/database.py
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import AsyncIterator, Generator

from sqlalchemy import create_engine
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
def get_cleaned_url(url: str | None, is_async: bool = True) -> str:
    """Strips query params like sslmode that crash specific drivers."""
    if not url:
        # Fallback for local testing if ENV is empty
        url = "postgresql://postgres:postgres@localhost:5432/bloodonal"

    clean_url = url.split("?")[0]

    if is_async and clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return clean_url


# =====================================================================
# ASYNC Engine (FastAPI Core)
# =====================================================================
ASYNC_DATABASE_URL = get_cleaned_url(settings.ASYNC_DATABASE_URL, is_async=True)

# Specific arguments for cloud providers like Neon/Render
async_connect_args = {
    "ssl": "require",
    "prepared_statement_cache_size": 0,
    "command_timeout": 60,
    "timeout": 60
} if "neon.tech" in ASYNC_DATABASE_URL else {}

# ✅ Updated: Now uses dynamic pool settings from config.py to handle >291 connections
async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    connect_args=async_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Primary FastAPI dependency for async DB sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except SQLAlchemyError as exc:
            logger.exception("⚠️ DB session error (async): %s", exc)
            raise
        finally:
            await session.close()


# Alias for broader compatibility across your routes
get_db = get_async_session

# =====================================================================
# SYNC Engine (Alembic Migrations / Admin Scripts)
# =====================================================================
SYNC_DATABASE_URL = get_cleaned_url(settings.SYNC_DATABASE_URL, is_async=False)

sync_connect_args = {
    "sslmode": "require",
    "connect_timeout": 60
} if SYNC_DATABASE_URL and "neon.tech" in SYNC_DATABASE_URL else {}

if SYNC_DATABASE_URL:
    sync_engine = create_engine(
        SYNC_DATABASE_URL,
        connect_args=sync_connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=settings.DB_POOL_SIZE,  # ✅ Match async scaling
        max_overflow=settings.DB_MAX_OVERFLOW  # ✅ Match async scaling
    )
    SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)
else:
    SyncSessionLocal = None


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
# Lifecycle Initialization
# =====================================================================

async def init_db() -> None:
    """
    Creates tables using SQLAlchemy metadata.
    Explicitly imports all models to populate the Base.metadata registry.
    """
    # 1. Financial & Usage Models
    from app.models.payment import Payment
    from app.models.wallet import Wallet
    from app.models.usage_counter import UsageCounter
    from app.data.models import Usage

    # 2. ✅ Modular Services (2026 Stack)
    from app.models.service_listing import ServiceListing
    # (If you still use ServiceRequest alongside ServiceListing, import it here too)
    # from app.models.servicemodel import ServiceRequest

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Database tables synced successfully.")

# =====================================================================
# Usage Helper Methods
# =====================================================================
# (Keep your existing get_free_usage_count and other query helpers down here)