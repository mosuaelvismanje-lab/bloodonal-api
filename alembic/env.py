import asyncio
import logging
import os
import sys
import ssl
from logging.config import fileConfig

# 1️ Load your .env so that Pydantic’s Settings sees the real Neon credentials
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# 2️ Allow imports from your application
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import settings     # now has real ASYNC_DATABASE_URL
from app.database import Base

# ——— Alembic configuration —————————————————————————————————————————————————

config = context.config
# Override the URL in alembic.ini with the ASYNC_DATABASE_URL from your settings
config.set_main_option("sqlalchemy.url", settings.ASYNC_DATABASE_URL)

if config.config_file_name:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.runtime.migration")
target_metadata = Base.metadata

# ——— Offline Migrations ————————————————————————————————————————————————

def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    logger.info("Running offline migrations against URL: %s", url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

# ——— Online Migrations ————————————————————————————————————————————————

def do_run_migrations(connection):
    logger.info("Applying migrations online")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    # Create a default SSL context (Neon requires SSL)
    ssl_ctx = ssl.create_default_context()
    # If you have a custom CA bundle, you can do:
    # ssl_ctx = ssl.create_default_context(cafile="/path/to/ca.pem")

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": ssl_ctx},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()

# ——— Entrypoint ————————————————————————————————————————————————————

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
