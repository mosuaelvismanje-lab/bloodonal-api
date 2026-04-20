from __future__ import annotations

import logging
import ssl
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

# Dedicated logger for database events
logger = logging.getLogger("bloodonal.database")

# =====================================================================
# Declarative Base
# =====================================================================
Base = declarative_base()


# =====================================================================
# Helper: URL Sanitization
# =====================================================================
def get_cleaned_url(url: str | None, is_async: bool = True) -> str:
    """
    Strips query params like sslmode that crash specific drivers.
    Ensures the correct async driver prefix is present.
    """
    if not url:
        # Fallback for local development
        return "postgresql://postgres:postgres@localhost:5432/bloodonal"

    # Remove query parameters for clean connect_args management
    clean_url = url.split("?")[0]

    if is_async and clean_url.startswith("postgresql://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return clean_url


# =====================================================================
# ASYNC Engine (FastAPI Core)
# =====================================================================
ASYNC_DATABASE_URL = get_cleaned_url(settings.ASYNC_DATABASE_URL, is_async=True)

# 🛠️ VPN & NEON RESILIENCE SETTINGS
# We use an SSL context for asyncpg to handle handshakes more reliably over VPN.
# 'jit': 'off' reduces the 'warm-up' time for serverless compute nodes.
async_connect_args = {
    "prepared_statement_cache_size": 0,  # ✅ Required for Neon/PgBouncer compatibility
    "command_timeout": 60,               # ✅ Prevents long queries from timing out
    "timeout": 60,                       # ✅ Gives the OS 60 seconds to resolve DNS and handshake
    "server_settings": {
        "jit": "off",
        "application_name": "bloodonal_api_async"
    },
}

if "neon.tech" in ASYNC_DATABASE_URL:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Adjust based on your security requirements
    async_connect_args["ssl"] = ctx

# ✅ Refined engine for high-latency environments & Cold Starts
async_engine: AsyncEngine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,  # Set to settings.DEBUG only when debugging SQL
    future=True,
    pool_pre_ping=True,      # ✅ Verifies connection health before use
    pool_recycle=300,        # ✅ 5 minutes. 120s is too aggressive and causes unnecessary reconnections
    pool_timeout=60,         # ✅ NEW: Tells SQLAlchemy to wait 60s for Neon to wake up before throwing a timeout
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
            logger.error("❌ DB session error (async): %s", exc)
            await session.rollback()
            raise
        finally:
            await session.close()


# Alias for compatibility
get_db = get_async_session

# =====================================================================
# SYNC Engine (Alembic Migrations / Admin Scripts)
# =====================================================================
SYNC_DATABASE_URL = get_cleaned_url(settings.SYNC_DATABASE_URL, is_async=False)

sync_connect_args = {
    "sslmode": "require",
    "connect_timeout": 60, # ✅ Increased from 30 to match async cold-start tolerance
    "application_name": "bloodonal_api_sync"
} if SYNC_DATABASE_URL and "neon.tech" in SYNC_DATABASE_URL else {}

if SYNC_DATABASE_URL:
    sync_engine = create_engine(
        SYNC_DATABASE_URL,
        connect_args=sync_connect_args,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=60,       # ✅ NEW: Wait for pool to furnish a connection
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW
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
    except Exception as e:
        session.rollback()
        logger.error("❌ Sync session error: %s", e)
        raise
    finally:
        session.close()


# =====================================================================
# Lifecycle Initialization
# =====================================================================

async def init_db() -> None:
    """
    Initializes database tables. Safe to call on application startup.
    """
    # Import all models to ensure they are registered with Base.metadata
    from app.models.payment import Payment
    from app.models.wallet import Wallet
    from app.models.usage_counter import UsageCounter
    from app.data.models import Usage
    from app.models.service_listing import ServiceListing

    try:
        async with async_engine.begin() as conn:
            # Uncomment below to reset DB (WARNING: Destructive)
            # await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables initialized/synced.")
    except Exception as e:
        logger.error("❌ Failed to initialize database: %s", e)
        # We don't raise here to allow the app to attempt to start regardless
        # but the error is logged for visibility.

# =====================================================================
# Usage Helper Methods
# =====================================================================
# Example: Placeholder for your specific query logic
# async def get_free_usage_count(user_id: str, session: AsyncSession):
#     ...