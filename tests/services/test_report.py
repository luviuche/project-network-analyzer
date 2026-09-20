"""
Tests for services/report.py — the deterministic rule layer.

These tests never touch the LLM layer: the structured report is built
with no client, no API key and no network. That is why, unlike the agent
tests, nothing here has to force fallback mode.
"""

from pathlib import Path

import pytest

from project_network_analyzer.domain.analysis import AnalysisResult, StructuralAnalyzer
from project_network_analyzer.domain.network import Network
from project_network_analyzer.infrastructure.loader import load_network
from project_network_analyzer.services.report import build_structured_report

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "proyecto_software.json"


@pytest.fixture
def context():
    network = load_network(DATA_FILE)
    return network, network.validate(), StructuralAnalyzer(network).analyze()


def test_report_contains_every_section(context):
    network, validation, analysis = context
    report = build_structured_report(network, validation, analysis)

    assert "VALIDACIÓN ESTRUCTURAL" in report
    assert "ANÁLISIS ESTRUCTURAL" in report
    assert "HALLAZGOS DETECTADOS POR REGLAS" in report
    assert "σ" in report
    assert network.project_name in report


def test_report_detects_the_key_patterns(context):
    network, validation, analysis = context
    report = build_structured_report(network, validation, analysis)

    assert "12 caminos" in report
    assert "PUNTO DE ARTICULACIÓN" in report
    assert "B (" in report and "N (" in report           # B and N are articulation points
    assert "V* = {A, B, N, O}" in report
    assert "paralelo" in report


def test_report_works_on_an_invalid_network():
    """The rule layer must explain the problem, not break."""
    net = Network("ciclica")
    for n in ("X", "Y"):
        net.add_activity(n, n)
    net.add_precedence("X", "Y")
    net.add_precedence("Y", "X")
    validation = net.validate()

    # No analysis available (not a DAG): an "empty" result is passed just
    # to check the validation report is still produced.
    empty = AnalysisResult(
        topological_order=[], paths=[], path_count=0,
        centrality={}, critical_nodes=[], max_sigma=0,
        bottlenecks=[], articulation_points=[],
        initial=[], final=[], intermediate=[], generations=[],
    )
    report = build_structured_report(net, validation, empty)
    assert "INVÁLIDA" in report
    assert "ciclo" in report.lower()
