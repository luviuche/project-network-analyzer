"""
Alembic environment: runs migrations against PostgreSQL.

The URL comes from, in order: `sqlalchemy.url` set on the Alembic config
(the test suite does this to target its own database), then
PNA_DATABASE_URL through `config.load_settings()`.

Only online mode is supported: migrations run against a live database,
never as generated SQL scripts.
"""

from logging.config import fileConfig

from alembic import context

from project_network_analyzer.config import load_settings
from project_network_analyzer.infrastructure.db.models import Base
from project_network_analyzer.infrastructure.db.session import build_engine

config = context.config

if config.config_file_name is not None:
    # Keep loggers configured by the caller (pytest, the app) working.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url") or load_settings().database_url
    if not url:
        raise RuntimeError(
            "No database configured: set PNA_DATABASE_URL (see .env.example)."
        )
    return url


def run_migrations_online() -> None:
    engine = build_engine(_database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline (--sql) mode is not supported.")
run_migrations_online()
