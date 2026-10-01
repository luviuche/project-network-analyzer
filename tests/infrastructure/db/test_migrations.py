"""
Tests for the Alembic migrations, against PostgreSQL.

The session fixture already migrates down to nothing and back up to
head, so a broken upgrade or downgrade fails the whole database suite.
What is checked here is that the migrations and the models agree: a
model change without a migration must not slip through.
"""

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from project_network_analyzer.infrastructure.db.models import Base

TABLES = {"networks", "activities", "precedences", "analyses", "interpretations"}


def test_migrations_match_the_models(db_engine):
    with db_engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_downgrade_removes_every_table(db_engine, alembic_config):
    try:
        command.downgrade(alembic_config, "base")
        assert TABLES.isdisjoint(inspect(db_engine).get_table_names())
    finally:
        command.upgrade(alembic_config, "head")
    assert TABLES <= set(inspect(db_engine).get_table_names())
