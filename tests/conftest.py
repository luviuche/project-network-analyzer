"""
Shared fixtures for the tests that need PostgreSQL.

They run against the database named by PNA_TEST_DATABASE_URL, read from
the environment or from `.env`. When it is not set, every test that
asks for `db_engine` or `db_session` is skipped with that reason, and
the rest of the suite runs as usual.

The schema is built with the real Alembic migrations — downgraded to
nothing, then upgraded to head — so the migrations are exercised on every
run. Each test then works inside a transaction that is rolled back, so
tests never see each other's rows.

Because the schema is dropped, the fixture refuses any database whose
name does not end in "_test": pointing this at a real database by
mistake must not wipe it.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from project_network_analyzer.infrastructure.db.session import (
    build_engine,
    normalize_database_url,
)

ROOT = Path(__file__).resolve().parents[1]


def _test_database_url() -> str | None:
    # Read .env without loading it into os.environ.
    return (
        os.environ.get("PNA_TEST_DATABASE_URL")
        or dotenv_values(ROOT / ".env").get("PNA_TEST_DATABASE_URL")
        or None
    )


@pytest.fixture(scope="session")
def db_url() -> str:
    url = _test_database_url()
    if not url:
        pytest.skip("PNA_TEST_DATABASE_URL is not set (see .env.example)")
    database = make_url(normalize_database_url(url)).database or ""
    if not database.endswith("_test"):
        pytest.fail(
            f"Refusing to use database {database!r} for tests: its schema is "
            "dropped and rebuilt, so its name must end in '_test'."
        )
    return url


@pytest.fixture(scope="session")
def alembic_config(db_url) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    # ConfigParser interpolation: a literal % in a password must be doubled.
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def db_engine(db_url, alembic_config) -> Iterator[Engine]:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    engine = build_engine(db_url)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Iterator[Session]:
    """
    A session inside an outer transaction that is always rolled back.
    `commit()` in the code under test releases a savepoint instead of
    committing for real.
    """
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
