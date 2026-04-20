# app/db/session.py
# G:\pycharm\bloodonal-api\app\db\session.py
from __future__ import annotations

# Import the updated objects from your database config
from app.database import (
    get_db,
    async_engine,
    AsyncSessionLocal,
    Base  # Added Base here in case other files import it from session
)

# ✅ ALIASES: This prevents the "cannot import name 'engine'" error in main.py
engine = async_engine
session_factory = AsyncSessionLocal

# ✅ Ensure all names are accessible to the rest of the app
__all__ = ["get_db", "engine", "session_factory", "async_engine", "AsyncSessionLocal", "Base"]