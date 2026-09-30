"""
Tests for infrastructure/db/session.py — no database needed.
"""

import pytest

from project_network_analyzer.infrastructure.db.session import (
    build_engine,
    normalize_database_url,
)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgresql://localhost/pna", "postgresql+psycopg://localhost/pna"),
        # The scheme hosting providers often hand out.
        ("postgres://u:p@host:5432/pna", "postgresql+psycopg://u:p@host:5432/pna"),
        # An explicit driver is the caller's choice.
        ("postgresql+psycopg://localhost/pna", "postgresql+psycopg://localhost/pna"),
    ],
)
def test_normalize_database_url(url, expected):
    assert normalize_database_url(url) == expected


def test_building_an_engine_does_not_connect():
    """The API must be able to start while the database is still down."""
    engine = build_engine("postgresql://localhost:1/unreachable")
    assert engine.url.drivername == "postgresql+psycopg"
    engine.dispose()
