"""
Tests for infrastructure/rendering.py — drawing the graph.

The image itself is not asserted pixel by pixel; what is asserted is
that the drawing is REPRODUCIBLE and that it does not mutate the domain
object it was handed.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from project_network_analyzer.domain.analysis import StructuralAnalyzer
from project_network_analyzer.domain.network import Network
from project_network_analyzer.infrastructure.rendering import GraphRenderer

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "proyecto_software.json"


@pytest.fixture
def renderer() -> GraphRenderer:
    network = Network.from_dict(json.loads(DATA_FILE.read_text(encoding="utf-8")))
    return GraphRenderer(network, StructuralAnalyzer(network).analyze())


def test_render_writes_a_png(renderer, tmp_path):
    out = renderer.render(tmp_path / "sub" / "graph.png")
    assert out.is_file()
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_positions_cover_every_node(renderer):
    positions = renderer._positions()
    assert set(positions) == set(renderer.network.activities)


def test_positions_follow_the_generation_order(renderer):
    """
    Within a column, nodes must be laid out in the order given by
    `AnalysisResult.generations`, which is sorted. This is the property
    that makes the drawing reproducible.
    """
    positions = renderer._positions()
    directions = set()
    for generation in renderer.analysis.generations:
        ys = [positions[node][1] for node in generation]
        if len(ys) > 1:
            directions.add("asc" if ys == sorted(ys) else "desc")
            assert ys in (sorted(ys), sorted(ys, reverse=True)), (
                f"generation {generation} is not laid out monotonically: {ys}"
            )
        # Same column: every node in a generation shares the x coordinate.
        xs = {round(positions[node][0], 9) for node in generation}
        assert len(xs) == 1

    # Monotonic per generation is not enough: every column must run the
    # same way, or the order is incidental rather than derived from
    # `generations`.
    assert len(directions) == 1, f"inconsistent vertical direction: {directions}"


def test_rendering_does_not_mutate_the_network(renderer):
    """The renderer draws; it must not write attributes on the domain graph."""
    before = {n: dict(d) for n, d in renderer.network.graph.nodes(data=True)}
    renderer._positions()
    after = {n: dict(d) for n, d in renderer.network.graph.nodes(data=True)}
    assert before == after


def test_layout_is_stable_across_hash_seeds():
    """
    Regression: the layout used to be derived from a node attribute, and
    networkx grouped those nodes into SETS. The vertical order inside a
    column then followed set iteration order, so the rendered image
    changed from run to run under Python's hash randomisation.

    Two subprocesses with different PYTHONHASHSEED must agree.
    """
    script = textwrap.dedent(
        f"""
        import json
        from project_network_analyzer.domain.analysis import StructuralAnalyzer
        from project_network_analyzer.domain.network import Network
        from project_network_analyzer.infrastructure.rendering import GraphRenderer

        data = json.loads(open({str(DATA_FILE)!r}, encoding="utf-8").read())
        network = Network.from_dict(data)
        renderer = GraphRenderer(network, StructuralAnalyzer(network).analyze())
        positions = renderer._positions()
        print(json.dumps({{k: [round(c, 9) for c in v] for k, v in positions.items()}},
                         sort_keys=True))
        """
    )

    def run(seed: str) -> str:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT / "src"),
                 "PATH": "/usr/bin:/bin"},
        )
        return result.stdout

    assert run("0") == run("1")
