import os
import pytest
from sqlalchemy import text
# Import the engine and session logic directly from your app
from app.db.session import engine, AsyncSessionLocal

# This decorator checks if the test is running in GitHub Actions.
# If 'GITHUB_ACTIONS' environment variable is true, it skips the test.
@pytest.mark.skipif(
    os.getenv("GITHUB_ACTIONS") == "true",
    reason="Skipping DB connection test in GitHub Actions (No local DB available)."
)
@pytest.mark.asyncio
async def test_connection():
    """
    Test database connectivity using the central app configuration.
    This ensures that SSL and asyncpg settings are working correctly.
    """
    try:
        # 1. Test the engine connection (Low level)
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            scalar = result.scalar()
            assert scalar == 1, f"Expected 1 from database, but got {scalar}"

        # 2. Test the session factory (High level - what the API uses)
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT now()"))
            db_time = result.scalar()
            assert db_time is not None
            print(f"\n✅ Connection Successful! Database time: {db_time}")

    except Exception as e:
        # If this fails with 'sslmode=require', check if your .env file
        # is overriding the ASYNC_DATABASE_URL without the SSL parameter.
        pytest.fail(f"Database connection failed: {str(e)}")

    finally:
        # Clean up connection pool after the test
        await engine.dispose()
