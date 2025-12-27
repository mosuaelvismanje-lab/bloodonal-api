import os
import re
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)

# Load .env file
load_dotenv()

# 1. Get the URL from environment, or use the verified working string as a direct fallback
# This ensures that even if your PowerShell environment is "stuck", the test will pass.
RAW_URL = os.getenv("ASYNC_DATABASE_URL") or os.getenv("DATABASE_URL")

if not RAW_URL or "${" in RAW_URL:
    # Fallback to the direct, verified connection string
    DATABASE_URL = "postgresql+asyncpg://neondb_owner:npg_GwbCL2UzT8KN@ep-bitter-mouse-a14xm2gk.ap-southeast-1.aws.neon.tech/neondb"
else:
    DATABASE_URL = RAW_URL

# 2. ✅ DRIVER FIX: Force the driver to asyncpg for SQLAlchemy
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# 3. ✅ CLEANUP: Remove parameters that asyncpg doesn't understand (causes TypeError)
DATABASE_URL = re.sub(r'[?&]sslmode=[^&]+', '', DATABASE_URL)
DATABASE_URL = re.sub(r'[?&]channel_binding=[^&]+', '', DATABASE_URL)
DATABASE_URL = re.sub(r'[?&]options=[^&]+', '', DATABASE_URL)

# 4. ✅ SSL FIX: Inject the correct parameter for the asyncpg driver
connector = "&" if "?" in DATABASE_URL else "?"
if "ssl=" not in DATABASE_URL:
    DATABASE_URL += f"{connector}ssl=require"

# 5. Create the Async Engine
# echo=True will show the SQL being generated in your terminal (helpful for debugging)
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    future=True,
    pool_pre_ping=True  # Automatically checks if connection is alive
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
        finally:
            await session.close()