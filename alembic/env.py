import sys
import os
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import pool, create_engine
from alembic import context

# 1. Add project root to PATH
sys.path.append(str(Path(__file__).resolve().parents[1]))

# 2. Import tools
from app.database import Base, get_cleaned_url
from app.config import settings
import app.models  # noqa: F401

# 3. Alembic Config setup
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# ---------------------------------------------------------------------
# 4. Standardized URL Logic for Alembic (Sync)
# ---------------------------------------------------------------------
# Use the same verified password logic as the rest of the app
RAW_URL = os.getenv("DATABASE_URL") or settings.DATABASE_URL
CLEAN_SYNC_URL = get_cleaned_url(RAW_URL, is_async=False)

config.set_main_option("sqlalchemy.url", CLEAN_SYNC_URL)

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    # Fix for Neon: Synchronous connections (like Alembic)
    # need sslmode passed in connect_args
    connect_args = {}
    if "neon.tech" in CLEAN_SYNC_URL:
        connect_args = {"sslmode": "require"}

    connectable = create_engine(
        CLEAN_SYNC_URL,
        poolclass=pool.NullPool,
        connect_args=connect_args
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
