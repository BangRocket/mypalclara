"""Alembic environment configuration for Clara database migrations.

This module configures Alembic to:
- Use DATABASE_URL environment variable for production (PostgreSQL)
- Fall back to SQLite for local development
- Import Base metadata from mypalclara.db.models for autogenerate support
"""

import os
from logging.config import fileConfig

from dotenv import load_dotenv

load_dotenv()

from alembic import context
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Override sqlalchemy.url with DATABASE_URL if set (production PostgreSQL)
if os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))

# Interpret the config file for Python logging — ONLY when nothing has configured
# logging yet (i.e. the standalone `alembic` CLI). When migrations run in-process
# (db.connection.run_alembic_migrations at gateway/adapter startup), the app's
# logging is already set up; fileConfig would replace its handlers, drop the root
# level to WARNING, and (by default) disable every existing logger — silently
# muting all gateway logs, including errors, for the rest of the process.
import logging

if config.config_file_name is not None and not logging.getLogger().handlers:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Import Base metadata for autogenerate support
# This allows Alembic to detect schema changes against our models
from mypalclara.db.models import Base

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
