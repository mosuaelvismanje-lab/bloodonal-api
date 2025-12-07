import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

# Load database URL from environment variables
ASYNC_DATABASE_URL = os.getenv(
    "ASYNC_DATABASE_URL",
    "postgresql+asyncpg://neondb_owner:npg_5yc9FbUSihGp@ep-bitter-mouse-a14xm2gk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
)

# Create async engine
engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@pytest.mark.asyncio
async def test_connection():
    """Test database connectivity."""
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            assert row[0] == 1, "Test query did not return expected result"
    finally:
        await engine.dispose()

# Optional: allow running as standalone script
if __name__ == "__main__":
    asyncio.run(test_connection())

