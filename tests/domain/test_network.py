"""
Tests for domain/network.py — the Network class and structural validation.

Cover: construction from deserialised data and its independence from
declaration order, deterministic accessors, the model's four constraints
(acyclicity, weak connectivity, source, sink) and the domain error
(`NetworkStructureError`).

Reading files is tested separately, in
`tests/infrastructure/test_loader.py`: the domain no longer touches disk.
"""

import json
from pathlib import Path

import pytest

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.domain.network import Network, ValidationResult

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "proyecto_software.json"


def _sample_network() -> Network:
    """The real case, built without going through the infrastructure layer."""
    return Network.from_dict(json.loads(DATA_FILE.read_text(encoding="utf-8")))


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def software_network() -> Network:
    """The real sample case: 15 activities."""
    return _sample_network()


@pytest.fixture
def chain_network() -> Network:
    """Minimal valid DAG: A → B → C (source A, sink C)."""
    net = Network("cadena")
    for n in ("A", "B", "C"):
        net.add_activity(n, f"act-{n}")
    net.add_precedence("A", "B")
    net.add_precedence("B", "C")
    return net


# --------------------------------------------------------------------- #
# Construction from data
# --------------------------------------------------------------------- #


def test_from_dict_basic_structure(software_network):
    assert len(software_network) == 15
    assert software_network.graph.number_of_edges() == 20
    assert software_network.activities == list("ABCDEFGHIJKLMNO")
    assert software_network.project_name.startswith("Desarrollo de Aplicación Web")


def test_from_dict_single_source_and_sink(software_network):
    assert software_network.sources == ["A"]
    assert software_network.sinks == ["O"]


def test_name_of_returns_a_readable_name(software_network):
    assert software_network.name_of("A") == "Levantamiento de requisitos"
    with pytest.raises(NetworkStructureError):
        software_network.name_of("ZZZ")


def test_from_dict_is_order_independent():
    """An activity may be declared before its predecessor."""
    data = {
        "proyecto": {"nombre": "orden"},
        "actividades": [
            {"id": "B", "nombre": "b", "precedentes": ["A"]},
            {"id": "A", "nombre": "a", "precedentes": []},
        ],
    }
    red = Network.from_dict(data)
    assert red.precedences == [("A", "B")]
    assert red.sources == ["A"] and red.sinks == ["B"]


def test_from_dict_without_activities():
    with pytest.raises(NetworkStructureError):
        Network.from_dict({"actividades": []})


def test_desde_dict_default_name():
    """With no "proyecto" block, the caller decides the name."""
    data = {"actividades": [{"id": "A", "nombre": "a", "precedentes": []}]}
    assert Network.from_dict(data).project_name == "red"
    assert Network.from_dict(data, "mi-red").project_name == "mi-red"


# --------------------------------------------------------------------- #
# Structural validation (the model's constraints)
# --------------------------------------------------------------------- #


def test_valid_network(software_network):
    v = software_network.validate()
    assert isinstance(v, ValidationResult)
    assert v.is_valid
    assert v.is_acyclic and v.is_weakly_connected
    assert v.sources == ["A"] and v.sinks == ["O"]
    assert v.detected_cycle == []


def test_minimal_chain_is_valid(chain_network):
    assert chain_network.validate().is_valid


def test_cycle_detection():
    net = Network("ciclica")
    for n in ("X", "Y", "Z"):
        net.add_activity(n, n)
    net.add_precedence("X", "Y")
    net.add_precedence("Y", "Z")
    net.add_precedence("Z", "X")

    assert not net.is_acyclic()
    cycle = net.detect_cycle()
    assert cycle[0] == cycle[-1]               # the cycle closes
    assert set("XYZ").issubset(set(cycle))

    v = net.validate()
    assert not v.is_valid
    assert not v.is_acyclic
    assert v.detected_cycle == cycle


def test_not_weakly_connected():
    """Two disconnected components: A→B and C→D."""
    net = Network("desconexa")
    for n in ("A", "B", "C", "D"):
        net.add_activity(n, n)
    net.add_precedence("A", "B")
    net.add_precedence("C", "D")

    v = net.validate()
    assert v.is_acyclic
    assert not v.is_weakly_connected
    assert not v.is_valid


def test_empty_graph_is_not_valid():
    net = Network("vacia")
    v = net.validate()
    assert not v.is_weakly_connected
    assert not v.is_valid


def test_require_valid_raises():
    net = Network("ciclica")
    for n in ("X", "Y"):
        net.add_activity(n, n)
    net.add_precedence("X", "Y")
    net.add_precedence("Y", "X")
    with pytest.raises(NetworkStructureError):
        net.require_valid()


def test_require_valid_returns_the_result(chain_network):
    v = chain_network.require_valid()
    assert isinstance(v, ValidationResult) and v.is_valid


# --------------------------------------------------------------------- #
# Construction errors
# --------------------------------------------------------------------- #


def test_duplicate_activity():
    net = Network("t")
    net.add_activity("A", "a")
    with pytest.raises(NetworkStructureError):
        net.add_activity("A", "otra")


def test_unknown_predecessor():
    net = Network("t")
    net.add_activity("A", "a")
    with pytest.raises(NetworkStructureError):
        net.add_precedence("NO_EXISTE", "A")


def test_self_precedence_is_rejected():
    net = Network("t")
    net.add_activity("A", "a")
    with pytest.raises(NetworkStructureError):
        net.add_precedence("A", "A")


# --------------------------------------------------------------------- #
# Utilities / representation
# --------------------------------------------------------------------- #


def test_validation_summary_states_the_verdict(software_network):
    text = software_network.validate().summary()
    assert "VÁLIDA" in text
    assert "Fuentes" in text and "Sumideros" in text


def test_len_and_repr(software_network):
    assert len(software_network) == 15
    assert "|V|=15" in repr(software_network)
    assert "|E|=20" in repr(software_network)
