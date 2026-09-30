"""
Tests for infrastructure/loader.py — reading networks from disk.

This is the only layer that touches the filesystem, so the tests needing
real files (`tmp_path`) live here. The domain is tested with plain
dictionaries, in `tests/domain/test_network.py`.
"""

import json
from pathlib import Path

import pytest

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.infrastructure.loader import load_network

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "software_project.json"


def test_loads_the_real_sample_case():
    network = load_network(DATA_FILE)
    assert len(network) == 15
    assert network.graph.number_of_edges() == 20
    assert network.project_name.startswith("Web Application Development")


def test_accepts_a_path_given_as_text():
    assert len(load_network(str(DATA_FILE))) == 15


def test_missing_file_raises_the_domain_error():
    """Callers should only ever have to handle NetworkStructureError."""
    with pytest.raises(NetworkStructureError):
        load_network(ROOT / "data" / "missing.json")


def test_falls_back_to_the_file_name_as_project_name(tmp_path):
    data = {"activities": [{"id": "A", "name": "a", "predecessors": []}]}
    path = tmp_path / "my-project.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    assert load_network(path).project_name == "my-project"


@pytest.mark.parametrize(
    ("content", "fragment"),
    [
        (b'{"activities": [', "not valid JSON"),
        (b"\xff\xfe{}", "not UTF-8"),
        (b"[1, 2]", "JSON object"),
    ],
)
def test_unusable_file_raises_the_domain_error(tmp_path, content, fragment):
    """
    Regression: these used to escape as JSONDecodeError, UnicodeDecodeError
    and AttributeError, and the CLI printed a traceback.
    """
    path = tmp_path / "broken.json"
    path.write_bytes(content)

    with pytest.raises(NetworkStructureError, match=fragment):
        load_network(path)


def test_json_error_points_at_the_line(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text('{\n  "activities": [\n    {"id": "A",}\n  ]\n}', encoding="utf-8")

    with pytest.raises(NetworkStructureError, match="line 3"):
        load_network(path)
