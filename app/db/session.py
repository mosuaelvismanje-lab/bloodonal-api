from app.database import (
    get_db as master_get_db,
    async_engine,
    AsyncSessionLocal
)

# 1. engine alias
# Uses the cleaned engine from app/database.py
engine = async_engine

# 2. session_factory alias
# Uses the session maker from app/database.py
session_factory = AsyncSessionLocal

# 3. get_db alias
# Keeps your routers working without changing their code
get_db = master_get_db

# Clean export
__all__ = ["get_db", "engine", "session_factory"]