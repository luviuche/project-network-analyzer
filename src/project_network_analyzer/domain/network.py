"""
network.py — Mathematical model of the project network.

A project is a directed acyclic graph (DAG)

        G = (V, E)

where:
    - V = the set of project activities.
    - E ⊆ V × V = precedence relations. The edge (P, A) exists when
      activity P precedes A, that is, P must finish before A can start.

`Network` builds the graph with `networkx` and validates the four
structural constraints of the model:

    1. Acyclicity      : G contains no directed cycle.
    2. Weak connectivity: the underlying undirected graph is connected.
    3. Source node(s)  : ∃ v ∈ V with in-degree  δ⁻(v) = 0.
    4. Sink node(s)    : ∃ v ∈ V with out-degree δ⁺(v) = 0.

This module does NOT run the structural analysis (paths, centrality,
articulation points): that is `analysis.py`. Here the structure is only
built and validated.

It does not read from disk either: `from_dict` takes data that has
already been deserialised. Obtaining it — from a file, an HTTP body or a
database row — is `infrastructure/loader.py`. The domain stays pure.

Note on wire format: the input keys are Spanish ("proyecto",
"actividades", "precedentes") because that is the shape of the sample
data file. Renaming them is a data-format decision, not a code one.

Report and error text is Spanish on purpose: it is user-facing output,
while identifiers, docstrings and comments are English.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from project_network_analyzer.domain.errors import NetworkStructureError


@dataclass
class ValidationResult:
    """
    Structured outcome of validating the model's constraints.

    A pure data object (deterministic and serialisable) so that tests,
    the report layer and the agent can all consume it unambiguously.
    """

    is_acyclic: bool
    is_weakly_connected: bool
    sources: list[str]
    sinks: list[str]
    # When the graph is NOT acyclic, the nodes of the detected cycle.
    detected_cycle: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """
        The network is structurally valid when it satisfies all four
        constraints: acyclic, weakly connected, and with at least one
        source and one sink.
        """
        return (
            self.is_acyclic
            and self.is_weakly_connected
            and len(self.sources) >= 1
            and len(self.sinks) >= 1
        )

    def summary(self) -> str:
        """Readable summary of the outcome (for the report and debugging)."""
        verdict = "VÁLIDA" if self.is_valid else "INVÁLIDA"
        lines = [
            f"Validación estructural: {verdict}",
            f"  - Acíclica          : {'sí' if self.is_acyclic else 'NO'}",
            f"  - Débilmente conexa : {'sí' if self.is_weakly_connected else 'NO'}",
            f"  - Fuentes  δ⁻(v)=0  : {', '.join(self.sources) or '(ninguna)'}",
            f"  - Sumideros δ⁺(v)=0 : {', '.join(self.sinks) or '(ninguno)'}",
        ]
        if not self.is_acyclic and self.detected_cycle:
            lines.append(
                f"  - Ciclo detectado   : {' → '.join(self.detected_cycle)}"
            )
        return "\n".join(lines)


class Network:
    """
    Project network modelled as a DAG G = (V, E).

    Each activity is a node carrying `nombre` and `descripcion`
    attributes. Each precedence relation (P precedes A) is a directed
    edge P → A.
    """

    def __init__(self, project_name: str, description: str = "") -> None:
        self.project_name: str = project_name
        self.description: str = description
        # The underlying directed graph: the canonical representation of G.
        self.graph: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def add_activity(
        self, activity_id: str, name: str, description: str = ""
    ) -> None:
        """
        Add a node (activity) to V.

        Raises NetworkStructureError if the id already exists: duplicate
        ids would make the network ambiguous.
        """
        if activity_id in self.graph:
            raise NetworkStructureError(
                f"Actividad duplicada: '{activity_id}' ya existe en la red."
            )
        self.graph.add_node(activity_id, nombre=name, descripcion=description)

    def add_precedence(self, predecessor: str, activity: str) -> None:
        """
        Add the edge `predecessor → activity` to E.

        Models the relation: `predecessor` must finish before `activity`
        starts. Both nodes must already exist in V.
        """
        for node in (predecessor, activity):
            if node not in self.graph:
                raise NetworkStructureError(
                    f"Precedencia inválida: la actividad '{node}' no existe. "
                    f"(Relación '{predecessor}' → '{activity}')."
                )
        if predecessor == activity:
            # A v→v self-loop is a trivial cycle: it breaks acyclicity.
            raise NetworkStructureError(
                f"Una actividad no puede precederse a sí misma: '{predecessor}'."
            )
        self.graph.add_edge(predecessor, activity)

    @classmethod
    def from_dict(cls, data: dict, default_name: str = "red") -> "Network":
        """
        Build a Network from already-deserialised data of the form:

            {
              "proyecto": {"nombre": ..., "descripcion": ...},
              "actividades": [
                {"id": "A", "nombre": ..., "descripcion": ...,
                 "precedentes": ["..."]},
                ...
              ]
            }

        Activities are loaded first (V) and precedences second (E), so the
        order in which they appear in the data does not matter.

        `default_name` is used when the "proyecto" block carries no name;
        the caller picks a sensible value (e.g. the file name).
        """
        meta = data.get("proyecto", {})
        network = cls(
            project_name=meta.get("nombre", default_name),
            description=meta.get("descripcion", ""),
        )

        activities = data.get("actividades", [])
        if not activities:
            raise NetworkStructureError(
                "Los datos no contienen actividades "
                "('actividades' vacío o ausente)."
            )

        # Step 1: load every node (V).
        for act in activities:
            network.add_activity(
                activity_id=act["id"],
                name=act.get("nombre", act["id"]),
                description=act.get("descripcion", ""),
            )

        # Step 2: load the precedences (E) once V is complete.
        for act in activities:
            for predecessor in act.get("precedentes", []):
                network.add_precedence(predecessor, act["id"])

        return network

    # ------------------------------------------------------------------ #
    # Structural accessors
    # ------------------------------------------------------------------ #

    @property
    def activities(self) -> list[str]:
        """V: activity ids, sorted so the result is deterministic."""
        return sorted(self.graph.nodes)

    @property
    def precedences(self) -> list[tuple[str, str]]:
        """E: edges (predecessor, activity), sorted."""
        return sorted(self.graph.edges)

    @property
    def sources(self) -> list[str]:
        """
        Source nodes: activities with in-degree δ⁻(v) = 0 (no predecessors,
        so they are the project's starting activities).
        """
        return sorted(v for v in self.graph.nodes if self.graph.in_degree(v) == 0)

    @property
    def sinks(self) -> list[str]:
        """
        Sink nodes: activities with out-degree δ⁺(v) = 0 (they precede
        nothing, so they are the project's final activities).
        """
        return sorted(v for v in self.graph.nodes if self.graph.out_degree(v) == 0)

    def name_of(self, activity_id: str) -> str:
        """Readable name of an activity, given its id."""
        if activity_id not in self.graph:
            raise NetworkStructureError(f"Actividad inexistente: '{activity_id}'.")
        return self.graph.nodes[activity_id].get("nombre", activity_id)

    # ------------------------------------------------------------------ #
    # Structural validation (the model's constraints)
    # ------------------------------------------------------------------ #

    def is_acyclic(self) -> bool:
        """
        Constraint 1 — acyclicity.

        True when G contains no directed cycle. Delegated to networkx
        (topological sort / DFS based).
        """
        return nx.is_directed_acyclic_graph(self.graph)

    def detect_cycle(self) -> list[str]:
        """
        Return the node sequence of a directed cycle if one exists, or an
        empty list when the graph is acyclic. Serves as the evidence for
        explaining why a network is invalid.
        """
        try:
            cycle_edges = nx.find_cycle(self.graph, orientation="original")
        except nx.NetworkXNoCycle:
            return []
        # find_cycle returns edges (u, v, dir); rebuild the node sequence.
        nodes = [u for u, _v, *_ in cycle_edges]
        nodes.append(cycle_edges[-1][1])  # close the cycle with the last v
        return nodes

    def is_weakly_connected(self) -> bool:
        """
        Constraint 2 — weak connectivity.

        True when the underlying UNDIRECTED graph is connected, i.e. every
        activity belongs to the same component (no disconnected
        sub-networks). An empty graph does not count as connected.
        """
        if self.graph.number_of_nodes() == 0:
            return False
        return nx.is_weakly_connected(self.graph)

    def validate(self) -> ValidationResult:
        """
        Evaluate the model's four constraints and return a
        `ValidationResult` (deterministic, no side effects).
        """
        acyclic = self.is_acyclic()
        return ValidationResult(
            is_acyclic=acyclic,
            is_weakly_connected=self.is_weakly_connected(),
            sources=self.sources,
            sinks=self.sinks,
            detected_cycle=[] if acyclic else self.detect_cycle(),
        )

    def require_valid(self) -> ValidationResult:
        """
        Like `validate()`, but raises `NetworkStructureError` when the
        network breaks a constraint. Useful to fail early in the
        orchestrator, before the analysis.
        """
        result = self.validate()
        if not result.is_valid:
            raise NetworkStructureError(
                "La red no es estructuralmente válida:\n" + result.summary()
            )
        return result

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        """Number of activities |V|."""
        return self.graph.number_of_nodes()

    def __repr__(self) -> str:
        return (
            f"Network(project={self.project_name!r}, "
            f"|V|={self.graph.number_of_nodes()}, "
            f"|E|={self.graph.number_of_edges()})"
        )
