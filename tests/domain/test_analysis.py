"""
Tests for domain/analysis.py — structural analysis of the DAG.

Cover: a valid and deterministic topological order, the count and shape
of the source→sink paths, σ(v) centrality (the DP cross-checked against
exhaustive enumeration), critical nodes V*, bottlenecks, articulation
points, classification, generations (antichains) and the safety limit on
enumeration.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

from project_network_analyzer.domain.analysis import AnalysisResult, StructuralAnalyzer
from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.domain.network import Network

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "proyecto_software.json"

# Expected values for the sample case (computed by hand and by DP).
EXPECTED_SIGMA = {
    "A": 12, "B": 12, "C": 9, "D": 3, "E": 3, "F": 6, "G": 6, "H": 6,
    "I": 8, "J": 4, "K": 8, "L": 8, "M": 4, "N": 12, "O": 12,
}


def _sample_network() -> Network:
    """The real case, built without going through the infrastructure layer."""
    return Network.from_dict(json.loads(DATA_FILE.read_text(encoding="utf-8")))


@pytest.fixture
def analyzer() -> StructuralAnalyzer:
    return StructuralAnalyzer(_sample_network())


@pytest.fixture
def result(analyzer) -> AnalysisResult:
    return analyzer.analyze()


# --------------------------------------------------------------------- #
# Topological order
# --------------------------------------------------------------------- #


def test_topological_order_is_valid(analyzer):
    order = analyzer.topological_order()
    pos = {n: i for i, n in enumerate(order)}
    for u, v in analyzer.graph.edges:
        assert pos[u] < pos[v], f"edge {u}->{v} violates the topological order"


def test_topological_order_is_deterministic(analyzer):
    assert analyzer.topological_order() == analyzer.topological_order()


# --------------------------------------------------------------------- #
# Source → sink paths
# --------------------------------------------------------------------- #


def test_path_count(analyzer):
    assert analyzer.path_count() == 12


def test_paths_are_valid(analyzer):
    paths, truncated = analyzer.source_to_sink_paths()
    assert not truncated
    assert len(paths) == 12
    sources, sinks = set(analyzer.network.sources), set(analyzer.network.sinks)
    for path in paths:
        assert path[0] in sources
        assert path[-1] in sinks
        for u, v in zip(path, path[1:]):
            assert analyzer.graph.has_edge(u, v)


def test_enumeration_limit_truncates_but_count_stays_exact(analyzer):
    paths, truncated = analyzer.source_to_sink_paths(limit=5)
    assert truncated
    assert len(paths) == 5
    # The DP count does not depend on enumeration: it stays exact.
    assert analyzer.path_count() == 12


# --------------------------------------------------------------------- #
# σ(v) centrality and critical nodes
# --------------------------------------------------------------------- #


def test_centrality_exact_values(analyzer):
    assert analyzer.path_centrality() == EXPECTED_SIGMA


def test_centrality_dp_matches_enumeration(analyzer):
    """σ(v) by DP == number of enumerated paths containing v."""
    sigma = analyzer.path_centrality()
    paths, _ = analyzer.source_to_sink_paths()
    count = Counter()
    for path in paths:
        for node in path:
            count[node] += 1
    assert sigma == dict(count)


def test_critical_nodes(analyzer):
    critical, maximum = analyzer.critical_nodes()
    assert critical == ["A", "B", "N", "O"]
    assert maximum == 12


# --------------------------------------------------------------------- #
# Bottlenecks and articulation points
# --------------------------------------------------------------------- #


def test_bottlenecks(analyzer):
    # σ(v) == total number of paths -> every path goes through v.
    assert analyzer.bottlenecks() == ["A", "B", "N", "O"]


def test_articulation_points(analyzer):
    # A and O are mandatory but degree 1: they do not disconnect the network.
    assert analyzer.articulation_points() == ["B", "N"]


# --------------------------------------------------------------------- #
# Classification and parallelism
# --------------------------------------------------------------------- #


def test_classification(analyzer):
    classes = analyzer.classify_activities()
    assert classes["initial"] == ["A"]
    assert classes["final"] == ["O"]
    assert set(classes["intermediate"]) == set("BCDEFGHIJKLMN")
    assert "A" not in classes["intermediate"] and "O" not in classes["intermediate"]


def test_generations_are_antichains(analyzer):
    """There can be no edges within a single generation."""
    generations = analyzer.generations()
    assert generations[0] == ["A"]
    assert generations[-1] == ["O"]
    for gen in generations:
        for u in gen:
            for v in gen:
                assert not analyzer.graph.has_edge(u, v)


def test_parallel_pairs(analyzer):
    pairs = set(analyzer.parallel_pairs())
    assert ("C", "E") in pairs          # both depend on B, incomparable
    assert ("A", "O") not in pairs      # A reaches O: they are comparable


# --------------------------------------------------------------------- #
# Aggregate result and edge cases
# --------------------------------------------------------------------- #


def test_analyze_returns_consistent_result(result):
    assert isinstance(result, AnalysisResult)
    assert result.path_count == 12
    assert result.critical_nodes == ["A", "B", "N", "O"]
    assert result.max_sigma == 12
    assert not result.paths_truncated
    assert "Orden topológico" in result.summary()


def test_analyzer_rejects_a_cyclic_graph():
    net = Network("ciclica")
    for n in ("X", "Y"):
        net.add_activity(n, n)
    net.add_precedence("X", "Y")
    net.add_precedence("Y", "X")
    with pytest.raises(NetworkStructureError):
        StructuralAnalyzer(net)
