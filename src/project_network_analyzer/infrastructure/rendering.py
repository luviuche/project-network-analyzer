"""
rendering.py — Drawing the project network graph.

Draws the DAG G = (V, E) with `networkx` + `matplotlib` and saves it to
`outputs/grafo_red.png`. The drawing is STRUCTURAL: it shows no time or
cost, only the topology and the structural roles the
`StructuralAnalyzer` found.

Layout: multipartite by topological GENERATIONS (each column is a phase;
activities in the same column can run in parallel), left to right from
the source(s) to the sink(s).

Visual encoding:
  - Fill colour  = structural role (source / sink / critical / normal).
  - Thick purple border = articulation point (a hard bottleneck).
  - Label = the activity id and its centrality σ(v).

No interactive backend (Agg): it works with no graphical environment, as
running the CLI on any machine requires.

The legend and title text is Spanish because it is user-facing output;
the identifiers, docstrings and comments around it are English.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend: must come before pyplot

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import networkx as nx

from project_network_analyzer.domain.analysis import AnalysisResult
from project_network_analyzer.domain.network import Network

# Palette (structural role -> fill colour).
_COLOR_SOURCE = "#2e7d32"       # green : initial activity (δ⁻=0)
_COLOR_SINK = "#c62828"         # red   : final activity   (δ⁺=0)
_COLOR_CRITICAL = "#ef6c00"     # orange: critical node V* = argmax σ(v)
_COLOR_INTERMEDIATE = "#90caf9"  # blue  : intermediate activity
_BORDER_ARTICULATION = "#6a1b9a"  # purple: articulation point


class GraphRenderer:
    """
    Produces the graph image from a `Network` and its `AnalysisResult`.
    It recomputes nothing: it only draws what was already analysed.
    """

    def __init__(self, network: Network, analysis: AnalysisResult) -> None:
        self.network = network
        self.analysis = analysis
        self.graph: nx.DiGraph = network.graph

    # ------------------------------------------------------------------ #
    # Node layout
    # ------------------------------------------------------------------ #

    def _positions(self) -> dict[str, tuple[float, float]]:
        """
        Multipartite layout: every node goes to the column matching the
        index of its topological generation. The graph then reads by
        phases from left to right, with parallel activities lined up
        vertically in the same column.
        """
        layer: dict[str, int] = {}
        for index, generation in enumerate(self.analysis.generations):
            for node in generation:
                layer[node] = index
        nx.set_node_attributes(self.graph, layer, name="capa")
        # align="vertical": each subset on a vertical, phases along x.
        return nx.multipartite_layout(self.graph, subset_key="capa", align="vertical")

    # ------------------------------------------------------------------ #
    # Per-node styling
    # ------------------------------------------------------------------ #

    def _color_for(self, node: str) -> str:
        """Fill colour by structural role (in order of priority)."""
        if node in self.analysis.initial:
            return _COLOR_SOURCE
        if node in self.analysis.final:
            return _COLOR_SINK
        if node in self.analysis.critical_nodes:
            return _COLOR_CRITICAL
        return _COLOR_INTERMEDIATE

    def _border_style(self) -> tuple[list[str], list[float]]:
        """
        Border per node: thick purple for an articulation point (a hard
        structural bottleneck), thin grey otherwise.
        """
        colors: list[str] = []
        widths: list[float] = []
        articulation = set(self.analysis.articulation_points)
        for node in self.graph.nodes:
            if node in articulation:
                colors.append(_BORDER_ARTICULATION)
                widths.append(3.0)
            else:
                colors.append("#37474f")
                widths.append(1.0)
        return colors, widths

    def _labels(self) -> dict[str, str]:
        """Label per node: its id and its centrality σ(v)."""
        sigma = self.analysis.centrality
        return {n: f"{n}\nσ={sigma.get(n, 0)}" for n in self.graph.nodes}

    # ------------------------------------------------------------------ #
    # Image generation
    # ------------------------------------------------------------------ #

    def render(self, output_path: str | Path = "outputs/grafo_red.png") -> Path:
        """
        Draw the graph and save it as a PNG. Returns the file path, and
        creates the output directory when it does not exist.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        positions = self._positions()
        node_colors = [self._color_for(n) for n in self.graph.nodes]
        border_colors, border_widths = self._border_style()

        # Canvas proportional to the number of phases and the widest one.
        phase_count = max(len(self.analysis.generations), 1)
        widest_phase = max((len(g) for g in self.analysis.generations), default=1)
        figure, axis = plt.subplots(
            figsize=(max(10, 1.7 * phase_count), max(6, 1.6 * widest_phase))
        )

        nx.draw_networkx_edges(
            self.graph,
            positions,
            ax=axis,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=16,
            edge_color="#78909c",
            width=1.4,
            node_size=2000,
            connectionstyle="arc3,rad=0.05",
        )
        nx.draw_networkx_nodes(
            self.graph,
            positions,
            ax=axis,
            node_color=node_colors,
            edgecolors=border_colors,
            linewidths=border_widths,
            node_size=2000,
        )
        nx.draw_networkx_labels(
            self.graph,
            positions,
            ax=axis,
            labels=self._labels(),
            font_size=9,
            font_color="#102027",
            font_weight="bold",
        )

        critical = ", ".join(self.analysis.critical_nodes)
        axis.set_title(
            f"Red estructural — {self.network.project_name}\n"
            f"V* (críticos, σ máx={self.analysis.max_sigma}): {critical}   "
            f"|   {self.analysis.path_count} caminos fuente→sumidero",
            fontsize=12,
        )
        axis.legend(
            handles=[
                Patch(facecolor=_COLOR_SOURCE, edgecolor="#37474f", label="Fuente (inicial)"),
                Patch(facecolor=_COLOR_SINK, edgecolor="#37474f", label="Sumidero (final)"),
                Patch(facecolor=_COLOR_CRITICAL, edgecolor="#37474f", label="Crítico V* = argmax σ(v)"),
                Patch(facecolor=_COLOR_INTERMEDIATE, edgecolor="#37474f", label="Intermedia"),
                Line2D(
                    [0], [0], marker="o", color="w", label="Punto de articulación",
                    markerfacecolor=_COLOR_INTERMEDIATE, markeredgecolor=_BORDER_ARTICULATION,
                    markeredgewidth=3, markersize=14,
                ),
            ],
            loc="lower center",
            ncol=3,
            fontsize=9,
            framealpha=0.9,
        )
        axis.set_axis_off()
        figure.tight_layout()
        figure.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(figure)  # free memory: never leave figures open
        return output_path
