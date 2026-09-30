"""
pipeline.py — Validate, analyse and report on a network in one call.

The sequence every caller needs: validate the network, run the
structural analysis only when it is valid, and turn the result into
findings and a text report. Keeping it here means the HTTP layer only
translates requests and responses, and holds no analysis logic of its
own.

Deterministic, no I/O and no API key: the LLM layer is not involved.
"""

from __future__ import annotations

from dataclasses import dataclass

from project_network_analyzer.domain.analysis import AnalysisResult, StructuralAnalyzer
from project_network_analyzer.domain.network import Network, ValidationResult
from project_network_analyzer.services.report import (
    build_structured_report,
    build_validation_report,
    detect_patterns,
    validation_findings,
)


@dataclass
class StructuralReport:
    """
    Everything the deterministic layer knows about one network.

    `analysis` is None when the network fails validation: paths and
    centrality are undefined on a graph that is not a valid DAG.
    """

    validation: ValidationResult
    analysis: AnalysisResult | None
    findings: list[str]
    text: str


def analyze_network(network: Network) -> StructuralReport:
    """Run the full deterministic pipeline on an already-built network."""
    validation = network.validate()
    if not validation.is_valid:
        return StructuralReport(
            validation=validation,
            analysis=None,
            findings=validation_findings(validation),
            text=build_validation_report(network, validation),
        )

    analysis = StructuralAnalyzer(network).analyze()
    return StructuralReport(
        validation=validation,
        analysis=analysis,
        findings=detect_patterns(network, validation, analysis),
        text=build_structured_report(network, validation, analysis),
    )
