import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url
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

# --------------------------------------------------------------------------
# CRITICAL FIX: Temporarily hardcode the known good, synchronous URL
# This bypasses the persistent issue of the old password being loaded from
# the application's environment variables (ASYNC_DATABASE_URL).
#
# This uses the correct driver (psycopg2), correct host (-pooler), and the
# correct NEW password (npg_GwbCL2UzT8KN).
# Remove this block after a successful migration.
# --------------------------------------------------------------------------
HARDCODED_SYNC_URL = "postgresql+psycopg2://neondb_owner:npg_GwbCL2UzT8KN@ep-bitter-mouse-a14xm2gk-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

config.set_main_option("sqlalchemy.url", HARDCODED_SYNC_URL)
# --------------------------------------------------------------------------


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
    # We must redefine connectable here as SQLAlchemy expects the URL to be available
    # in the config object when engine_from_config is called.
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
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