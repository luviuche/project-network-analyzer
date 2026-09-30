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
    add(f"PROJECT: {network.project_name}")
    if network.description:
        add(network.description)
    add(f"Activities |V| = {len(network)}   Precedences |E| = "
        f"{network.graph.number_of_edges()}")
    add("=" * 64)

    add("\n[1] STRUCTURAL VALIDATION")
    add(validation.summary())

    add("\n[2] STRUCTURAL ANALYSIS")
    add(analysis.summary())
    add("\nPath centrality σ(v) (source→sink paths through v):")
    for v, s in sorted(
        analysis.centrality.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        add(f"  {v} ({network.name_of(v)}): σ = {s}")

    add("\nActivity classification:")
    add(f"  Initial     : {_with_names(network, analysis.initial)}")
    add(f"  Final       : {_with_names(network, analysis.final)}")
    add(f"  Intermediate: {_with_names(network, analysis.intermediate)}")

    add("\nPhases (topological generations — parallel activities):")
    for i, generation in enumerate(analysis.generations):
        marker = "  ← parallel" if len(generation) > 1 else ""
        add(f"  Phase {i}: {_with_names(network, generation)}{marker}")

    add("\n[3] RULE-BASED FINDINGS")
    for finding in detect_patterns(network, validation, analysis):
        add(f"  - {finding}")

    return "\n".join(lines)


def build_validation_report(
    network: Network, validation: ValidationResult
) -> str:
    """
    The report for a network that fails validation. The structural
    analysis needs a valid DAG, so this stops at section [1] and says why.
    """
    return (
        f"PROJECT: {network.project_name}\n"
        f"{'=' * 64}\n\n"
        "[1] STRUCTURAL VALIDATION\n"
        f"{validation.summary()}\n\n"
        "The network breaks at least one of the model's constraints, so "
        "neither the structural analysis nor the rendering is run.\n"
    )


def _with_names(network: Network, ids: list[str]) -> str:
    """Format 'A (name), B (name)' so the report stays readable."""
    if not ids:
        return "(none)"
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
    findings = validation_findings(validation)

    n = analysis.path_count
    if n > 1:
        findings.append(
            f"There are {n} distinct structural paths from source to sink: "
            "the project admits several execution sequences."
        )
    elif n == 1:
        findings.append(
            "There is a single source→sink path: the network is a chain "
            "with no structural alternatives."
        )

    for v in analysis.articulation_points:
        findings.append(
            f"Node {v} ({network.name_of(v)}) is an ARTICULATION POINT: "
            "removing it would disconnect the network. It is a critical "
            "structural bottleneck; its risk is worth mitigating."
        )

    non_articulation = [
        b for b in analysis.bottlenecks
        if b not in analysis.articulation_points
    ]
    if non_articulation:
        findings.append(
            "EVERY path goes through: "
            f"{', '.join(non_articulation)}. They are mandatory in any "
            "execution (though they do not disconnect the network)."
        )

    if analysis.critical_nodes:
        findings.append(
            f"Critical nodes V* = {{{', '.join(analysis.critical_nodes)}}} "
            f"with maximum σ = {analysis.max_sigma}: they carry the most "
            "paths and are the most structurally sensitive."
        )

    # Parallelism in the first phase holding more than one activity.
    for i, generation in enumerate(analysis.generations):
        if len(generation) > 1:
            findings.append(
                f"Phase {i} has {len(generation)} activities that can run "
                f"in parallel: {', '.join(generation)}."
            )
            break

    parallel_phases = sum(
        1 for g in analysis.generations if len(g) > 1
    )
    if parallel_phases:
        findings.append(
            f"{parallel_phases} phase(s) show structural parallelism: "
            "they could shorten the project if resources permit."
        )

    return findings


def validation_findings(validation: ValidationResult) -> list[str]:
    """
    The findings that need only the validation result. They are all there
    is to say about a network that fails validation, since the analysis
    does not run on it.
    """
    findings: list[str] = []
    if not validation.is_valid:
        findings.append(
            "The network is NOT structurally valid: it breaks at least one "
            "of the model's constraints (see section [1])."
        )
        if validation.detected_cycle:
            findings.append(
                "A directed cycle was detected: "
                f"{' → '.join(validation.detected_cycle)}. A project "
                "cannot have circular dependencies."
            )
    return findings
