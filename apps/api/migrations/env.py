"""
Alembic environment. Supports both:
  - online mode (alembic upgrade head) against a real Postgres, and
  - offline mode (alembic upgrade head --sql) which emits SQL to stdout
    without a live connection — this is the mode used by
    scripts/validate_migrations_offline.sh in this sandbox, since no live
    PostgreSQL instance is reachable here (see
    docs/architecture/14-phase5-database-implementation.md "Migration
    Validation" for the full explanation).
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.getcwd())

import app.models as m  # noqa: E402  (registers all tables on Base.metadata)
from app.core.config import settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = m.Base.metadata

# Prefer the psycopg (sync) driver for Alembic — migrations run
# synchronously regardless of the app's async runtime engine.
db_url = os.environ.get("ALEMBIC_DATABASE_URL", settings.sqlalchemy_database_uri)
config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=False,  # Postgres supports native ALTER; batch mode is a SQLite concern
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
