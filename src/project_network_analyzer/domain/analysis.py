"""
analysis.py — Structural analysis of the project network.

Takes a `Network` that has already been built and validated (see
`network.py`) and computes its STRUCTURAL properties. Time, cost and
resources play no part: only the topology of the DAG G = (V, E).

What is computed:

  1. Topological order (a feasible execution order).
  2. Enumeration of the source → sink paths.
  3. Path centrality σ(v) and the critical nodes V* = argmax σ(v).
  4. Structural bottlenecks (nodes every path goes through) and the
     articulation points of the underlying undirected graph.
  5. Activity classification: initial, final, intermediate and parallel
     (topological generations / antichains).

The central formula — σ(v):

    σ(v) = (# paths source → v) · (# paths v → sink)

Computed with dynamic programming over the topological order in
O(|V| + |E|), which avoids the combinatorial blow-up of enumerating
paths:

    paths_to(v)   = 1                    if v is a source
                  = Σ paths_to(u)        for every edge u → v

    paths_from(v) = 1                    if v is a sink
                  = Σ paths_from(w)      for every edge v → w

The total number of source→sink paths is Σ paths_to(t) over every sink t
(equivalently Σ paths_from(s) over every source s).

Report text is Spanish on purpose: it is user-facing output, while
identifiers, docstrings and comments are English.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.domain.network import Network


@dataclass
class AnalysisResult:
    """
    Structured outcome of the analysis (deterministic and serialisable).

    Consumed by the report layer and, through it, by the agent. The LLM
    NEVER recomputes any of this: it only interprets it.
    """

    topological_order: list[str]
    paths: list[list[str]]
    path_count: int
    centrality: dict[str, int]             # σ(v) per activity
    critical_nodes: list[str]              # V* = argmax σ(v)
    max_sigma: int
    bottlenecks: list[str]                 # σ(v) == path_count
    articulation_points: list[str]         # underlying undirected graph
    initial: list[str]
    final: list[str]
    intermediate: list[str]
    generations: list[list[str]]           # antichains: parallel activities
    paths_truncated: bool = False          # True when the limit kicked in

    def summary(self) -> str:
        """Readable summary of the analysis (for the deterministic report)."""
        lineas = [
            f"Orden topológico   : {' → '.join(self.topological_order)}",
            f"Caminos f→s        : {self.path_count}"
            + (" (lista truncada)" if self.paths_truncated else ""),
            f"σ máximo           : {self.max_sigma}",
            f"Nodos críticos V*  : {', '.join(self.critical_nodes)}",
            f"Cuellos de botella : {', '.join(self.bottlenecks) or '(ninguno)'}",
            f"Ptos. articulación : {', '.join(self.articulation_points) or '(ninguno)'}",
            f"Iniciales          : {', '.join(self.initial)}",
            f"Finales            : {', '.join(self.final)}",
            f"Intermedias        : {', '.join(self.intermediate)}",
            f"Generaciones (||)  : {len(self.generations)} fases",
        ]
        return "\n".join(lineas)


class StructuralAnalyzer:
    """
    Computes the structural properties of a `Network`.

    The network is assumed to have been validated already (acyclic,
    weakly connected, with a source and a sink). If it is not acyclic the
    analysis is meaningless and aborts with `NetworkStructureError`.
    """

    # Safety limit for path ENUMERATION (the σ count has no limit because
    # it is O(|V|+|E|)). Guards against combinatorial blow-up.
    PATH_LIMIT = 10_000

    def __init__(self, network: Network) -> None:
        if not network.is_acyclic():
            raise NetworkStructureError(
                "El análisis estructural requiere un DAG: la red contiene "
                f"un ciclo {network.detect_cycle()}."
            )
        self.network = network
        self.graph: nx.DiGraph = network.graph

    # ------------------------------------------------------------------ #
    # 1. Topological order
    # ------------------------------------------------------------------ #

    def topological_order(self) -> list[str]:
        """
        A linear order of V in which every edge u→v has u before v: a
        feasible execution order for the activities.

        The lexicographical topological order is used so the result is
        deterministic (several valid orders exist).
        """
        return list(nx.lexicographical_topological_sort(self.graph))

    # ------------------------------------------------------------------ #
    # 2. Source → sink paths
    # ------------------------------------------------------------------ #

    def source_to_sink_paths(
        self, limit: int | None = PATH_LIMIT
    ) -> tuple[list[list[str]], bool]:
        """
        Enumerate every simple path from any source node to any sink node.
        In a DAG every path is simple.

        Returns (paths, truncated). When `limit` is reached, enumeration
        stops and `truncated=True` (the exact COUNT is still available via
        `path_count()`).
        """
        paths: list[list[str]] = []
        truncated = False
        for source in self.network.sources:
            for sink in self.network.sinks:
                for path in nx.all_simple_paths(self.graph, source, sink):
                    paths.append(path)
                    if limit is not None and len(paths) >= limit:
                        truncated = True
                        break
                if truncated:
                    break
            if truncated:
                break
        # Deterministic order.
        paths.sort()
        return paths, truncated

    # ------------------------------------------------------------------ #
    # 3. Path centrality σ(v) and critical nodes
    # ------------------------------------------------------------------ #

    def _paths_to(self) -> dict[str, int]:
        """
        Dynamic programming over the topological order:

            paths_to(v) = 1                 if v is a source
                        = Σ paths_to(u)      ∀ edge u→v

        Counts how many distinct paths reach v from some source.
        """
        to: dict[str, int] = {}
        for v in nx.topological_sort(self.graph):
            predecessors = list(self.graph.predecessors(v))
            if not predecessors:                       # v is a source
                to[v] = 1
            else:
                to[v] = sum(to[u] for u in predecessors)
        return to

    def _paths_from(self) -> dict[str, int]:
        """
        Dynamic programming over the reversed topological order:

            paths_from(v) = 1                  if v is a sink
                          = Σ paths_from(w)     ∀ edge v→w

        Counts how many distinct paths leave v towards some sink.
        """
        frm: dict[str, int] = {}
        for v in reversed(list(nx.topological_sort(self.graph))):
            successors = list(self.graph.successors(v))
            if not successors:                         # v is a sink
                frm[v] = 1
            else:
                frm[v] = sum(frm[w] for w in successors)
        return frm

    def path_centrality(self) -> dict[str, int]:
        """
        σ(v) = paths_to(v) · paths_from(v)

        The number of source→sink paths through v. Returned sorted by id
        so the result is deterministic.
        """
        to = self._paths_to()
        frm = self._paths_from()
        return {v: to[v] * frm[v] for v in sorted(self.graph.nodes)}

    def path_count(self) -> int:
        """
        Total number of source→sink paths.

        = Σ paths_to(t) over every sink t. Exact and O(|V|+|E|): it does
        not depend on enumerating the paths.
        """
        to = self._paths_to()
        return sum(to[t] for t in self.network.sinks)

    def critical_nodes(self) -> tuple[list[str], int]:
        """
        V* = argmax_{v ∈ V} σ(v).

        The structurally most critical nodes: those carrying the largest
        number of source→sink paths. Returns (V*, σ_max).
        """
        sigma = self.path_centrality()
        if not sigma:
            return [], 0
        maximum = max(sigma.values())
        critical = sorted(v for v, s in sigma.items() if s == maximum)
        return critical, maximum

    # ------------------------------------------------------------------ #
    # 4. Bottlenecks and articulation points
    # ------------------------------------------------------------------ #

    def bottlenecks(self) -> list[str]:
        """
        Nodes that EVERY source→sink path goes through, i.e. σ(v) equals
        the total number of paths.

        These are structural bottlenecks: a failure or block there affects
        every possible sequence of the project. By construction it
        includes the single source and sink, when there is only one of
        each.
        """
        total = self.path_count()
        sigma = self.path_centrality()
        return sorted(v for v, s in sigma.items() if s == total)

    def articulation_points(self) -> list[str]:
        """
        Articulation points of the underlying UNDIRECTED graph: nodes
        whose removal disconnects the network (increases the number of
        connected components).

        A stronger structural bottleneck than `bottlenecks`: not only does
        every path go through it, it is the only link between two parts of
        the project. Degree-1 nodes (a single source or sink) are NOT
        articulation points even though they are mandatory.
        """
        return sorted(nx.articulation_points(self.graph.to_undirected()))

    # ------------------------------------------------------------------ #
    # 5. Activity classification
    # ------------------------------------------------------------------ #

    def classify_activities(self) -> dict[str, list[str]]:
        """
        Classify V into:
          - initial     : source nodes (δ⁻(v) = 0).
          - final       : sink nodes   (δ⁺(v) = 0).
          - intermediate: the rest (δ⁻(v) > 0 and δ⁺(v) > 0).
        """
        initial = set(self.network.sources)
        final = set(self.network.sinks)
        intermediate = sorted(
            v for v in self.graph.nodes if v not in initial and v not in final
        )
        return {
            "initial": self.network.sources,
            "final": self.network.sinks,
            "intermediate": intermediate,
        }

    def generations(self) -> list[list[str]]:
        """
        Topological generations (antichains): each generation is a set of
        activities with no precedence among them whose predecessors are
        all in earlier generations. These are the activities that can run
        IN PARALLEL at that phase of the project.
        """
        return [sorted(gen) for gen in nx.topological_generations(self.graph)]

    def parallel_pairs(self) -> list[tuple[str, str]]:
        """
        Pairs of activities incomparable in the DAG's partial order: no
        directed path joins them either way, so they can run in parallel.
        A broader notion than `generations`, which additionally requires
        sharing a phase.
        """
        closure = nx.transitive_closure_dag(self.graph)
        nodes = sorted(self.graph.nodes)
        pairs: list[tuple[str, str]] = []
        for i, u in enumerate(nodes):
            for v in nodes[i + 1 :]:
                if not closure.has_edge(u, v) and not closure.has_edge(v, u):
                    pairs.append((u, v))
        return pairs

    # ------------------------------------------------------------------ #
    # Aggregate analysis
    # ------------------------------------------------------------------ #

    def analyze(self, path_limit: int | None = PATH_LIMIT) -> AnalysisResult:
        """
        Run the whole analysis and return an `AnalysisResult`
        (deterministic, no side effects). This is the input the report
        layer — and through it the agent — interprets, never recomputes.
        """
        paths, truncated = self.source_to_sink_paths(path_limit)
        sigma = self.path_centrality()
        critical, sigma_max = self.critical_nodes()
        classes = self.classify_activities()
        return AnalysisResult(
            topological_order=self.topological_order(),
            paths=paths,
            path_count=self.path_count(),
            centrality=sigma,
            critical_nodes=critical,
            max_sigma=sigma_max,
            bottlenecks=self.bottlenecks(),
            articulation_points=self.articulation_points(),
            initial=classes["initial"],
            final=classes["final"],
            intermediate=classes["intermediate"],
            generations=self.generations(),
            paths_truncated=truncated,
        )
