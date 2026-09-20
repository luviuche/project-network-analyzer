"""
report.py — The deterministic rule layer.

Takes a `ValidationResult` and an `AnalysisResult` and produces a
structured text report, spotting patterns with fixed rules (critical
paths, articulation points, parallel activities...).

Fully deterministic and testable: no I/O, no network, no API key. The
report is the system's complete output on its own, and it is also the
CONTEXT handed to the LLM layer (see `agent/llm_agent.py`).

IMPORTANT (the project's one rule): all the mathematics lives in
`domain/`. Here, numbers that have already been computed are turned into
structural statements; the LLM later puts those into prose, but never
recomputes them.

The report text is Spanish because it is user-facing output; the
identifiers, docstrings and comments around it are English.
"""

from __future__ import annotations

from project_network_analyzer.domain.analysis import AnalysisResult
from project_network_analyzer.domain.network import Network, ValidationResult


def build_structured_report(
    network: Network,
    validation: ValidationResult,
    analysis: AnalysisResult,
) -> str:
    """
    Build the structured text report from the model's results. This is
    the system's deterministic output.
    """
    lines: list[str] = []
    add = lines.append

    add("=" * 64)
    add(f"PROYECTO: {network.project_name}")
    if network.description:
        add(network.description)
    add(f"Actividades |V| = {len(network)}   Precedencias |E| = "
        f"{network.graph.number_of_edges()}")
    add("=" * 64)

    add("\n[1] VALIDACIÓN ESTRUCTURAL")
    add(validation.summary())

    add("\n[2] ANÁLISIS ESTRUCTURAL")
    add(analysis.summary())
    add("\nCentralidad de paso σ(v) (caminos f→s que pasan por v):")
    for v, s in sorted(
        analysis.centrality.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        add(f"  {v} ({network.name_of(v)}): σ = {s}")

    add("\nClasificación de actividades:")
    add(f"  Iniciales : {_with_names(network, analysis.initial)}")
    add(f"  Finales   : {_with_names(network, analysis.final)}")
    add(f"  Intermedias: {_with_names(network, analysis.intermediate)}")

    add("\nFases (generaciones topológicas — actividades en paralelo):")
    for i, generation in enumerate(analysis.generations):
        marker = "  ← paralelas" if len(generation) > 1 else ""
        add(f"  Fase {i}: {_with_names(network, generation)}{marker}")

    add("\n[3] HALLAZGOS DETECTADOS POR REGLAS")
    for finding in detect_patterns(network, validation, analysis):
        add(f"  - {finding}")

    return "\n".join(lines)


def _with_names(network: Network, ids: list[str]) -> str:
    """Format 'A (name), B (name)' so the report stays readable."""
    if not ids:
        return "(ninguna)"
    return ", ".join(f"{i} ({network.name_of(i)})" for i in ids)


def detect_patterns(
    network: Network,
    validation: ValidationResult,
    analysis: AnalysisResult,
) -> list[str]:
    """
    Deterministic rules that turn the analysis numbers into structural
    statements. These sentences are the raw material the LLM later puts
    into natural language.
    """
    findings: list[str] = []

    if not validation.is_valid:
        findings.append(
            "La red NO es estructuralmente válida: no se cumple alguna "
            "restricción del modelo (ver sección [1])."
        )
        if validation.detected_cycle:
            findings.append(
                "Se detectó un ciclo dirigido: "
                f"{' → '.join(validation.detected_cycle)}. Un proyecto "
                "no puede tener dependencias circulares."
            )

    n = analysis.path_count
    if n > 1:
        findings.append(
            f"Existen {n} caminos estructurales distintos de la fuente al "
            "sumidero: el proyecto admite múltiples secuencias de ejecución."
        )
    elif n == 1:
        findings.append(
            "Existe un único camino fuente→sumidero: la red es una cadena "
            "sin alternativas estructurales."
        )

    for v in analysis.articulation_points:
        findings.append(
            f"El nodo {v} ({network.name_of(v)}) es un PUNTO DE ARTICULACIÓN: "
            "su eliminación desconectaría la red. Es un cuello de botella "
            "estructural crítico; conviene mitigar su riesgo."
        )

    non_articulation = [
        b for b in analysis.bottlenecks
        if b not in analysis.articulation_points
    ]
    if non_articulation:
        findings.append(
            "Pasan TODOS los caminos por: "
            f"{', '.join(non_articulation)}. Son obligatorios en cualquier "
            "ejecución (aunque no desconectan la red)."
        )

    if analysis.critical_nodes:
        findings.append(
            f"Nodos críticos V* = {{{', '.join(analysis.critical_nodes)}}} "
            f"con σ máximo = {analysis.max_sigma}: concentran el mayor "
            "paso de caminos y son los más sensibles estructuralmente."
        )

    # Parallelism in the first phase holding more than one activity.
    for i, generation in enumerate(analysis.generations):
        if len(generation) > 1:
            findings.append(
                f"En la fase {i} hay {len(generation)} actividades que pueden "
                f"ejecutarse en paralelo: {', '.join(generation)}."
            )
            break

    parallel_phases = sum(
        1 for g in analysis.generations if len(g) > 1
    )
    if parallel_phases:
        findings.append(
            f"Hay {parallel_phases} fase(s) con paralelismo estructural: "
            "permiten acortar la ruta del proyecto si hay recursos."
        )

    return findings
