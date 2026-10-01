"""
Tests for infrastructure/db/repository.py, against PostgreSQL.

The central property is the round trip: a network saved and read back
rebuilds into the same graph — same nodes, same edges, same order — and
the analysis stored with it is exactly what the pipeline computes.
Interpretations are checked for their history: per network, newest first.
"""

import json
import uuid
from dataclasses import asdict
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from project_network_analyzer.domain.network import Network
from project_network_analyzer.infrastructure.db.models import NetworkRow, PrecedenceRow
from project_network_analyzer.infrastructure.db.repository import (
    InterpretationRepository,
    NetworkRepository,
    to_domain,
)
from project_network_analyzer.services.pipeline import analyze_network

ROOT = Path(__file__).resolve().parents[3]
DATA_FILE = ROOT / "data" / "software_project.json"


def _sample() -> Network:
    return Network.from_dict(json.loads(DATA_FILE.read_text(encoding="utf-8")))


def _cyclic() -> Network:
    return Network.from_dict(
        {
            "project": {"name": "cyclic"},
            "activities": [
                {"id": "X", "predecessors": ["Z"]},
                {"id": "Y", "predecessors": ["X"]},
                {"id": "Z", "predecessors": ["Y"]},
            ],
        }
    )


def _save(session, network: Network):
    return NetworkRepository(session).add(network, analyze_network(network))


def _reload(session, row):
    """Read the row back from the database, not from the identity map."""
    network_id = row.id
    session.expunge_all()
    return NetworkRepository(session).get(network_id)


# --------------------------------------------------------------------- #
# Round trip
# --------------------------------------------------------------------- #


def test_saved_network_rebuilds_into_the_same_graph(db_session):
    original = _sample()
    loaded = to_domain(_reload(db_session, _save(db_session, original)))

    assert loaded.project_name == original.project_name
    assert loaded.description == original.description
    assert list(loaded.graph.nodes(data=True)) == list(original.graph.nodes(data=True))
    # Edge iteration follows adjacency order, so this checks order too.
    assert list(loaded.graph.edges) == list(original.graph.edges)


def test_stored_analysis_is_what_the_pipeline_computes(db_session):
    network = _sample()
    expected = analyze_network(network)
    assert expected.analysis is not None
    stored = _reload(db_session, _save(db_session, network)).analysis

    assert stored.is_valid is True
    assert stored.analysis == asdict(expected.analysis)
    assert stored.validation == {**asdict(expected.validation), "is_valid": True}
    assert stored.findings == expected.findings
    assert stored.report == expected.text


def test_invalid_network_is_stored_without_analysis(db_session):
    network = _cyclic()
    row = _reload(db_session, _save(db_session, network))

    assert row.analysis.is_valid is False
    assert row.analysis.analysis is None
    # Declaration order is what decides which cycle is reported.
    assert to_domain(row).detect_cycle() == network.detect_cycle()
    # SQL NULL, not a JSON null.
    assert db_session.scalar(
        text("SELECT analysis IS NULL FROM analyses WHERE network_id = :id"),
        {"id": row.id},
    )


def test_a_repeated_predecessor_is_stored_once(db_session):
    network = Network.from_dict(
        {"activities": [{"id": "A"}, {"id": "B", "predecessors": ["A", "A"]}]}
    )
    row = _reload(db_session, _save(db_session, network))
    (_, b) = row.activities
    assert [link.predecessor_key for link in b.predecessor_links] == ["A"]


def test_get_unknown_id_returns_none(db_session):
    assert NetworkRepository(db_session).get(uuid.uuid4()) is None


# --------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------- #


def test_list_is_newest_first_with_a_total(db_session):
    first = _save(db_session, _sample())
    second = _save(db_session, _cyclic())
    repository = NetworkRepository(db_session)

    items, total = repository.list_summaries(limit=10, offset=0)
    assert total == 2
    assert [item.id for item in items] == [second.id, first.id]
    assert [(item.is_valid, item.activity_count) for item in items] == [
        (False, 3),
        (True, 15),
    ]

    page, total = repository.list_summaries(limit=1, offset=1)
    assert total == 2
    assert [item.id for item in page] == [first.id]


def test_report_and_existence_lookups(db_session):
    network = _sample()
    row = _save(db_session, network)
    repository = NetworkRepository(db_session)

    assert repository.exists(row.id) is True
    assert repository.get_report(row.id) == analyze_network(network).text

    missing = uuid.uuid4()
    assert repository.exists(missing) is False
    assert repository.get_report(missing) is None


# --------------------------------------------------------------------- #
# Interpretations
# --------------------------------------------------------------------- #


def test_interpretations_are_listed_per_network_newest_first(db_session):
    sample = _save(db_session, _sample())
    other = _save(db_session, _cyclic())
    repository = InterpretationRepository(db_session)

    first = repository.add(sample.id, None, "model-a", "General reading.")
    repository.add(other.id, None, "model-a", "About the other network.")
    second = repository.add(sample.id, "Which node is critical?", "model-b", "B.")
    db_session.expunge_all()

    items, total = repository.list_for(sample.id, limit=10, offset=0)
    assert total == 2
    assert [item.id for item in items] == [second.id, first.id]
    assert [(item.question, item.model, item.text) for item in items] == [
        ("Which node is critical?", "model-b", "B."),
        (None, "model-a", "General reading."),
    ]

    page, total = repository.list_for(sample.id, limit=1, offset=1)
    assert total == 2
    assert [item.id for item in page] == [first.id]


def test_interpretations_go_with_their_network(db_session):
    row = _save(db_session, _sample())
    InterpretationRepository(db_session).add(row.id, None, "model-a", "Text.")
    db_session.flush()

    # ON DELETE CASCADE, in the database itself.
    db_session.execute(NetworkRow.__table__.delete().where(NetworkRow.id == row.id))
    assert db_session.scalar(text("SELECT count(*) FROM interpretations")) == 0


# --------------------------------------------------------------------- #
# Constraints the database enforces on its own
# --------------------------------------------------------------------- #


def test_database_rejects_a_self_precedence(db_session):
    row = _save(db_session, _sample())
    db_session.add(
        PrecedenceRow(network_id=row.id, activity_key="B", predecessor_key="B", position=9)
    )
    with pytest.raises(IntegrityError, match="no_self_precedence"):
        db_session.flush()
    db_session.rollback()


def test_database_rejects_a_precedence_across_networks(db_session):
    """Both ends must be activities of the same network."""
    sample = _save(db_session, _sample())
    other = _save(db_session, _cyclic())
    assert other.id != sample.id
    db_session.add(
        PrecedenceRow(network_id=sample.id, activity_key="B", predecessor_key="X", position=9)
    )
    with pytest.raises(IntegrityError, match="fk_precedences_predecessor_activities"):
        db_session.flush()
    db_session.rollback()
