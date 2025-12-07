import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy import create_engine
from alembic import context

# -------------------------
# Add project root to PATH
# -------------------------
sys.path.append(str(Path(__file__).resolve().parents[1]))

# -------------------------
# Load models & metadata
# -------------------------
from app.database import Base
import app.models  # noqa: F401

target_metadata = Base.metadata

# -------------------------
# Alembic Config
# -------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# -------------------------
# Use sync DATABASE_URL from environment or settings
# -------------------------
from app.config import settings
import os

DATABASE_URL = os.getenv("DATABASE_URL") or settings.DATABASE_URL
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    # Convert async URL to sync URL for Alembic
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://", 1)

config.set_main_option("sqlalchemy.url", DATABASE_URL)

# -------------------------
# OFFLINE MODE
# -------------------------
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

# -------------------------
# ONLINE MODE
# -------------------------
def run_migrations_online():
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# -------------------------
# Execute
# -------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
