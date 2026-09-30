"""
Tests for api/networks.py — saved networks over HTTP.

The first group needs no database: it checks that the API degrades to a
503 when persistence is missing or down, while the stateless endpoints
keep working. The rest run against PostgreSQL through the `db_session`
fixture, and are skipped without PNA_TEST_DATABASE_URL.
"""

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from project_network_analyzer.api.app import create_app
from project_network_analyzer.api.shared import get_session
from project_network_analyzer.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, Settings

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "software_project.json"


def _settings(database_url: str | None = None) -> Settings:
    return Settings(
        api_key="",
        model=DEFAULT_MODEL,
        max_tokens=DEFAULT_MAX_TOKENS,
        database_url=database_url,
    )


@pytest.fixture
def sample() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


@pytest.fixture
def client(db_session) -> TestClient:
    """An app whose sessions all join the test's rolled-back transaction."""
    app = create_app(settings=_settings())

    def _session():
        yield db_session

    app.dependency_overrides[get_session] = _session
    return TestClient(app)


CYCLIC = {
    "project": {"name": "cyclic"},
    "activities": [
        {"id": "X", "predecessors": ["Y"]},
        {"id": "Y", "predecessors": ["X"]},
    ],
}


# --------------------------------------------------------------------- #
# Without a usable database (always run)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/networks"),
        ("get", "/networks"),
        ("get", f"/networks/{uuid.uuid4()}"),
    ],
)
def test_without_a_database_the_networks_endpoints_are_503(method, path, sample):
    client = TestClient(create_app(settings=_settings(database_url=None)))
    response = client.request(method, path, json=sample if method == "post" else None)
    assert response.status_code == 503
    assert "PNA_DATABASE_URL" in response.json()["detail"]


def test_stateless_endpoints_work_without_a_database(sample):
    client = TestClient(create_app(settings=_settings(database_url=None)))
    assert client.post("/analysis", json=sample).status_code == 200


def test_unreachable_database_is_503_not_500(sample):
    """Configured but down: nothing listens on port 1."""
    app = create_app(settings=_settings("postgresql://localhost:1/pna_test"))
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/networks", json=sample)
    assert response.status_code == 503
    assert response.json() == {"detail": "The database is unavailable."}


# --------------------------------------------------------------------- #
# Saving and reading back (PostgreSQL)
# --------------------------------------------------------------------- #


def test_create_returns_201_with_the_analysis(client, sample):
    response = client.post("/networks", json=sample)
    assert response.status_code == 201
    body = response.json()

    assert response.headers["location"].endswith(f"/networks/{body['id']}")
    assert body["activities"] == sample["activities"]

    # The stored analysis is the same one /analysis computes.
    analysis = client.post("/analysis", json=sample).json()
    for field in ("project", "validation", "analysis", "findings", "report"):
        assert body[field] == analysis[field]


def test_get_returns_what_create_returned(client, db_session, sample):
    created = client.post("/networks", json=sample).json()

    # Read back from the database rather than the session's identity map,
    # over a connection whose time zone is not UTC.
    db_session.expunge_all()
    db_session.execute(text("SET TIME ZONE 'America/Bogota'"))

    response = client.get(f"/networks/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_timestamps_are_utc(client, db_session, sample):
    """Regression: they used to come back in the database session's zone."""
    client.post("/networks", json=sample)
    db_session.expunge_all()
    db_session.execute(text("SET TIME ZONE 'America/Bogota'"))

    (item,) = client.get("/networks").json()["items"]
    assert item["created_at"].endswith("Z")


def test_saved_activities_show_the_resolved_defaults(client):
    payload = {"activities": [{"id": "A"}, {"id": "B", "predecessors": ["A"]}]}
    body = client.post("/networks", json=payload).json()

    assert body["project"] == {"name": "network", "description": ""}
    assert body["activities"] == [
        {"id": "A", "name": "A", "description": "", "predecessors": []},
        {"id": "B", "name": "B", "description": "", "predecessors": ["A"]},
    ]


def test_invalid_network_is_saved_with_its_verdict(client):
    response = client.post("/networks", json=CYCLIC)
    assert response.status_code == 201
    body = response.json()
    assert body["validation"]["is_valid"] is False
    assert body["analysis"] is None
    assert client.get(f"/networks/{body['id']}").json() == body


def test_unbuildable_network_is_422_and_nothing_is_saved(client):
    response = client.post("/networks", json={"activities": [{"id": "A", "predecessors": ["Q"]}]})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "network_structure"
    assert client.get("/networks").json()["total"] == 0


def test_unknown_id_is_404(client):
    response = client.get(f"/networks/{uuid.uuid4()}")
    assert response.status_code == 404


def test_malformed_id_is_422(client):
    assert client.get("/networks/not-a-uuid").status_code == 422


# --------------------------------------------------------------------- #
# Listing (PostgreSQL)
# --------------------------------------------------------------------- #


def test_list_pages_newest_first(client, sample):
    ids = [client.post("/networks", json=payload).json()["id"] for payload in (sample, CYCLIC, sample)]

    first = client.get("/networks", params={"limit": 2}).json()
    assert first["total"] == 3
    assert (first["limit"], first["offset"]) == (2, 0)
    assert [item["id"] for item in first["items"]] == [ids[2], ids[1]]
    assert first["items"][1] == {
        "id": ids[1],
        "name": "cyclic",
        "created_at": first["items"][1]["created_at"],
        "is_valid": False,
        "activity_count": 2,
    }

    second = client.get("/networks", params={"limit": 2, "offset": 2}).json()
    assert [item["id"] for item in second["items"]] == [ids[0]]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_rejects_out_of_range_paging(client, params):
    assert client.get("/networks", params=params).status_code == 422
