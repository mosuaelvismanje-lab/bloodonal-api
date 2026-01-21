import os
import logging
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

# Load .env file
load_dotenv()
log = logging.getLogger("bloodonal")

# 1. Get the URL from environment
RAW_URL = os.getenv("ASYNC_DATABASE_URL") or os.getenv("DATABASE_URL")

# Fallback to the direct, verified connection string if env is missing
if not RAW_URL or "${" in RAW_URL:
    DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_GwbCL2UzT8KN@ep-bitter-mouse-a14xm2gk.ap-southeast-1.aws.neon.tech/neondb"
else:
    DATABASE_URL = RAW_URL

# 2. ✅ DRIVER FIX: Ensure we use asyncpg for the async engine
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 3. ✅ THE "NUCLEAR" CLEANUP: Strip EVERYTHING after the '?'
# This is the most reliable way to ensure 'sslmode' or 'options' never reach the driver.
DATABASE_URL = DATABASE_URL.split("?")[0]

# 4. ✅ SSL FIX: Official connect_args approach
# We pass SSL settings directly to the driver as a Python dictionary.
connect_args = {}
if "neon.tech" in DATABASE_URL or os.getenv("RENDER") == "true":
    # Neon and Render both require SSL for production database connections
    connect_args = {"ssl": "require"}

# DEBUG: This will show up in your terminal so you can verify the URL is clean
print(f"--- Connecting to DB: {DATABASE_URL} ---")

# 5. Create the Async Engine
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args
)

# 6. Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db():
    """FastAPI dependency for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            log.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()