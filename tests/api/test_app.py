"""
Tests for api/app.py — the HTTP boundary.

The app is built with explicit `Settings` carrying no API key, so the
agent is pinned to fallback mode whatever the machine's environment or
`.env` holds: these tests never reach the Claude API.

The analysis itself is tested in `tests/domain/`; here the concern is
the contract — status codes, response shape, and that the numbers the
API returns are the domain's, untouched.
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from project_network_analyzer.api.app import create_app
from project_network_analyzer.config import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, Settings
from project_network_analyzer.domain.network import Network
from project_network_analyzer.services.pipeline import analyze_network

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "software_project.json"

NO_KEY = Settings(api_key="", model=DEFAULT_MODEL, max_tokens=DEFAULT_MAX_TOKENS)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(settings=NO_KEY))


@pytest.fixture
def sample() -> dict:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def _cyclic() -> dict:
    return {
        "project": {"name": "cyclic"},
        "activities": [
            {"id": "X", "predecessors": ["Y"]},
            {"id": "Y", "predecessors": ["X"]},
        ],
    }


# --------------------------------------------------------------------- #
# /health
# --------------------------------------------------------------------- #


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --------------------------------------------------------------------- #
# /analysis — valid network
# --------------------------------------------------------------------- #


def test_analysis_of_the_sample_case(client, sample):
    response = client.post("/analysis", json=sample)
    assert response.status_code == 200
    body = response.json()

    assert body["project"]["name"].startswith("Web Application Development")
    assert body["validation"]["is_valid"] is True
    assert body["validation"]["sources"] == ["A"]
    assert body["validation"]["sinks"] == ["O"]

    analysis = body["analysis"]
    assert analysis["path_count"] == 12
    assert len(analysis["paths"]) == 12
    assert analysis["critical_nodes"] == ["A", "B", "N", "O"]
    assert analysis["max_sigma"] == 12
    assert analysis["articulation_points"] == ["B", "N"]


def test_analysis_returns_the_domain_result_untouched(client, sample):
    """The API serialises the pipeline's output; it computes nothing."""
    expected = analyze_network(Network.from_dict(sample))
    assert expected.analysis is not None
    body = client.post("/analysis", json=sample).json()

    assert body["analysis"]["centrality"] == expected.analysis.centrality
    assert body["analysis"]["generations"] == expected.analysis.generations
    assert body["findings"] == expected.findings
    assert body["report"] == expected.text


def test_optional_fields_take_the_domain_defaults(client):
    payload = {"activities": [{"id": "A"}, {"id": "B", "predecessors": ["A"]}]}
    body = client.post("/analysis", json=payload).json()

    assert body["project"] == {"name": "network", "description": ""}
    assert body["analysis"]["path_count"] == 1
    assert "A (A)" in body["report"]  # a missing name falls back to the id


# --------------------------------------------------------------------- #
# /analysis — built but invalid: a 200 that says so
# --------------------------------------------------------------------- #


def test_cyclic_network_is_answered_not_rejected(client):
    response = client.post("/analysis", json=_cyclic())
    assert response.status_code == 200
    body = response.json()

    assert body["validation"]["is_valid"] is False
    assert body["validation"]["is_acyclic"] is False
    assert body["validation"]["detected_cycle"][0] == body["validation"]["detected_cycle"][-1]
    assert body["analysis"] is None
    assert any("cycle" in finding for finding in body["findings"])


# --------------------------------------------------------------------- #
# /analysis — cannot be built: 422 in one error format
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("activities", "fragment"),
    [
        ([{"id": "A"}, {"id": "A"}], "Duplicate activity"),
        ([{"id": "A", "predecessors": ["Q"]}], "'Q' does not exist"),
        ([{"id": "A", "predecessors": ["A"]}], "cannot precede itself"),
    ],
)
def test_domain_rejections_are_422(client, activities, fragment):
    response = client.post("/analysis", json={"activities": activities})
    assert response.status_code == 422
    (error,) = response.json()["detail"]
    assert error["type"] == "network_structure"
    assert fragment in error["msg"]


@pytest.mark.parametrize(
    "payload",
    [
        {"activities": []},                        # empty network
        {},                                        # no activities at all
        {"activities": [{"name": "no id"}]},       # activity without an id
        {"activities": [{"id": ""}]},              # blank id
        {"activities": [{"id": "A", "predecessors": "B"}]},  # not a list
    ],
)
def test_malformed_payloads_are_422(client, payload):
    response = client.post("/analysis", json=payload)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_body_that_is_not_json_is_422(client):
    response = client.post(
        "/analysis", content="{not json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------- #
# /interpretation — fallback mode (no network calls)
# --------------------------------------------------------------------- #


def test_interpretation_falls_back_without_a_key(client, sample):
    response = client.post("/interpretation", json={"network": sample})
    assert response.status_code == 200
    body = response.json()

    assert "fallback" in body["agent_mode"]
    assert body["interpretation"].startswith("[FALLBACK MODE")
    assert body["answer"] is None
    assert body["report"] == analyze_network(Network.from_dict(sample)).text


def test_interpretation_answers_a_question(client, sample):
    body = client.post(
        "/interpretation",
        json={"network": sample, "question": "Which node is the most critical?"},
    ).json()
    assert body["answer"].startswith("[FALLBACK MODE")


def test_interpretation_rejects_an_unbuildable_network(client):
    payload = {"network": {"activities": [{"id": "A", "predecessors": ["Q"]}]}}
    response = client.post("/interpretation", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "network_structure"


# --------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------- #


def test_bad_configuration_fails_at_startup(monkeypatch):
    """A broken PNA_MAX_TOKENS must stop the app from starting at all."""
    monkeypatch.setenv("PNA_MAX_TOKENS", "not-an-integer")
    with pytest.raises(ValueError, match="PNA_MAX_TOKENS"):
        create_app()
