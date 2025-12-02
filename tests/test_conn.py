# tests/test_conn.py

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
import os

# Load database URL from environment variables
ASYNC_DATABASE_URL = os.getenv(
    "ASYNC_DATABASE_URL",
    "postgresql+asyncpg://neondb_owner:npg_5yc9FbUSihGp@ep-bitter-mouse-a14xm2gk-pooler.ap-southeast-1.aws.neon.tech/neondb"
)

# Create async engine
engine = create_async_engine(ASYNC_DATABASE_URL, echo=True)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def test_connection():
    try:
        async with engine.connect() as conn:
            # Execute a simple test query
            result = await conn.execute(text("SELECT 1"))
            row = result.fetchone()
            print("Connection successful, test query result:", row[0])

        # Optional: close the engine
        await engine.dispose()
    except Exception as e:
        print("Connection failed:", e)

if __name__ == "__main__":
    asyncio.run(test_connection())
