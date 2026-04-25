"""Alembic environment for Who-Dis (Phase 9, WD-DB-02).

DATABASE_URL is sourced from the process env (injected by the SandCastle deploy
engine into the container). The Flask app's SQLAlchemy metadata is used as the
target so `alembic revision --autogenerate` diffs against the live model.
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Alembic Config object — gives access to alembic.ini values
config = context.config

# Configure Python logging from the .ini file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from env (the .ini intentionally leaves it blank)
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL env var is required for Alembic (set by the SandCastle deploy engine)."
    )
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Import the SQLAlchemy metadata target from the Flask app
# (app must be importable; alembic runs in the container's working dir = /app)
from app.database import db  # noqa: E402
import app.models  # noqa: E402,F401  -- ensure all model classes are registered on db.metadata

target_metadata = db.metadata


def run_migrations_offline() -> None:
    """Generate SQL without connecting to the DB."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a real DB connection."""
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
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
