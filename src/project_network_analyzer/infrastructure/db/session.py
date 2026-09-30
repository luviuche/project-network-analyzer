"""
session.py — Engine and session factory.

The engine connects lazily: building it touches nothing, so the API can
start while the database is still coming up, and reports it as
unavailable per request instead of refusing to boot.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# The driver this project installs. A bare "postgresql://" would make
# SQLAlchemy look for psycopg2, which is not a dependency.
_DRIVER_PREFIX = "postgresql+psycopg://"


def normalize_database_url(url: str) -> str:
    """
    Point a PostgreSQL URL at the psycopg 3 driver.

    Hosting providers hand out "postgres://" or "postgresql://" URLs; both
    are rewritten. A URL that already names a driver is left alone.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return _DRIVER_PREFIX + url[len(prefix):]
    return url


def build_engine(url: str) -> Engine:
    # pre_ping replaces connections the server dropped while idle.
    return create_engine(normalize_database_url(url), pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: responses are built from the rows right
    # after the commit, and reloading them would be a wasted round trip.
    return sessionmaker(bind=engine, expire_on_commit=False)
