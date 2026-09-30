"""
Tests for services/pipeline.py — validate, analyse and report in one call.

The pipeline adds no logic of its own, so what is pinned down is that it
wires the existing pieces together faithfully, and that an invalid
network gets a validation-only result instead of an exception.
"""

from pathlib import Path

from project_network_analyzer.domain.analysis import StructuralAnalyzer
from project_network_analyzer.domain.network import Network
from project_network_analyzer.infrastructure.loader import load_network
from project_network_analyzer.services.pipeline import analyze_network
from project_network_analyzer.services.report import (
    build_structured_report,
    detect_patterns,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "software_project.json"


def _cyclic_network() -> Network:
    net = Network("cyclic")
    for n in ("X", "Y"):
        net.add_activity(n, n)
    net.add_precedence("X", "Y")
    net.add_precedence("Y", "X")
    return net


def test_valid_network_matches_the_individual_layers():
    network = load_network(DATA_FILE)
    validation = network.validate()
    analysis = StructuralAnalyzer(network).analyze()

    result = analyze_network(network)

    assert result.validation == validation
    assert result.analysis == analysis
    assert result.findings == detect_patterns(network, validation, analysis)
    assert result.text == build_structured_report(network, validation, analysis)


def test_invalid_network_stops_at_validation():
    result = analyze_network(_cyclic_network())

    assert not result.validation.is_valid
    assert result.analysis is None
    assert "INVALID" in result.text
    assert any("cycle" in finding for finding in result.findings)


def test_disconnected_network_is_not_analysed():
    """Acyclic but in two pieces: still invalid, so still no analysis."""
    net = Network("disconnected")
    for n in ("A", "B", "C", "D"):
        net.add_activity(n, n)
    net.add_precedence("A", "B")
    net.add_precedence("C", "D")

    result = analyze_network(net)
    assert result.validation.is_acyclic
    assert result.analysis is None
    assert result.findings == [
        "The network is NOT structurally valid: it breaks at least one "
        "of the model's constraints (see section [1])."
    ]
