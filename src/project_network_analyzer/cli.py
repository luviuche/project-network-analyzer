"""
cli.py — The project orchestrator.

Chains the whole flow together:

    JSON  →  Network (domain)  →  validation  →  structural analysis
          →  rendering (PNG)   →  hybrid agent  →  reporte.txt

Run it with:

    PYTHONPATH=src python -m project_network_analyzer.cli

Optionally:

    PYTHONPATH=src python -m project_network_analyzer.cli \
        --datos data/otro.json --pregunta "¿...?" --modelo claude-sonnet-5

The mathematics lives in `domain/`; the agent only interprets. This
module computes nothing: it only coordinates.

The command-line flags and the console output are Spanish because they
are the user interface; the identifiers, docstrings and comments around
them are English.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from project_network_analyzer.agent.llm_agent import LLMAgent
from project_network_analyzer.domain.analysis import StructuralAnalyzer
from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.infrastructure.loader import load_network
from project_network_analyzer.infrastructure.rendering import GraphRenderer
from project_network_analyzer.services.report import build_structured_report

def _project_root(candidate: Path | None = None) -> Path:
    """
    Where `data/` and `outputs/` live.

    In a source checkout that is the repo root, two levels above this
    file (src/project_network_analyzer/ -> src/ -> root), so the CLI
    works from any directory. Installed as a wheel, this file sits in
    site-packages and that path is meaningless, so the working directory
    is used instead.
    """
    if candidate is None:
        candidate = Path(__file__).resolve().parents[2]
    return candidate if (candidate / "data").is_dir() else Path.cwd()


ROOT = _project_root()
DEFAULT_DATA_FILE = ROOT / "data" / "proyecto_software.json"
OUTPUT_DIR = ROOT / "outputs"


def _parse_args() -> argparse.Namespace:
    """Define and parse the command-line arguments."""
    p = argparse.ArgumentParser(
        description="Análisis estructural de una red de proyecto (Grupo 6)."
    )
    p.add_argument(
        "--datos",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Ruta al JSON del proyecto (por defecto: data/proyecto_software.json).",
    )
    p.add_argument(
        "--pregunta",
        type=str,
        default=None,
        help="Pregunta abierta para el agente sobre la red (opcional).",
    )
    p.add_argument(
        "--modelo",
        type=str,
        default=None,
        help="Modelo de Claude para la capa LLM (opcional; p. ej. "
        "claude-sonnet-5). Por defecto usa el del agente.",
    )
    return p.parse_args()


def _step(number: int, text: str) -> None:
    """Print a step marker on the console."""
    print(f"\n[{number}] {text}")


def main() -> int:
    """Run the whole flow. Returns the process exit code."""
    args = _parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUTPUT_DIR / "grafo_red.png"
    report_path = OUTPUT_DIR / "reporte.txt"

    print("=" * 64)
    print("  ANÁLISIS ESTRUCTURAL DE REDES DE PROYECTOS — GRUPO 6")
    print("=" * 64)

    # ---- 1. Load the network ----------------------------------------- #
    _step(1, f"Cargando la red desde: {args.datos}")
    try:
        network = load_network(args.datos)
    except NetworkStructureError as e:
        print(f"  ERROR al construir la red: {e}", file=sys.stderr)
        return 1
    print(f"  OK — {network!r}")

    # ---- 2. Structural validation ------------------------------------ #
    _step(2, "Validando las restricciones del modelo")
    validation = network.validate()
    print(validation.summary())

    # ---- 3. Agent: created early so an invalid network still gets a
    #        deterministic report explaining the problem --------------- #
    agent = LLMAgent(model=args.modelo)
    print(f"\n  Agente en modo: {agent.mode}")

    if not validation.is_valid:
        _step(3, "La red NO es válida: se omite el análisis estructural")
        print("  (El análisis de caminos/centralidad requiere un DAG válido.)")
        body = (
            f"PROYECTO: {network.project_name}\n"
            f"{'=' * 64}\n\n"
            "[1] VALIDACIÓN ESTRUCTURAL\n"
            f"{validation.summary()}\n\n"
            "La red no cumple alguna restricción del modelo, por lo que no "
            "se ejecuta el análisis estructural ni la visualización.\n"
        )
        _write_report(report_path, body, agent.mode, args.datos)
        print(f"\n  Reporte (parcial) escrito en: {report_path}")
        return 1

    # ---- 4. Structural analysis -------------------------------------- #
    _step(4, "Ejecutando el análisis estructural")
    analysis = StructuralAnalyzer(network).analyze()
    print(analysis.summary())

    # ---- 5. Rendering -------------------------------------------------#
    _step(5, "Generando la visualización del grafo")
    GraphRenderer(network, analysis).render(png_path)
    print(f"  OK — grafo guardado en: {png_path}")

    # ---- 6. Structured report + LLM interpretation ------------------- #
    _step(6, "Construyendo el reporte estructurado (capa determinista)")
    structured_report = build_structured_report(network, validation, analysis)
    print("  OK — reporte estructurado generado.")

    _step(7, "Interpretando el reporte (capa LLM o fallback)")
    interpretation = agent.interpret(structured_report)
    print("  OK — interpretación obtenida.")

    question_answer = None
    if args.pregunta:
        _step(8, f"Respondiendo la pregunta: «{args.pregunta}»")
        question_answer = agent.answer(args.pregunta, structured_report)
        print("  OK — respuesta obtenida.")

    # ---- 7. Write the final report ----------------------------------- #
    body = structured_report + "\n\n"
    body += "=" * 64 + "\n"
    body += "[4] INTERPRETACIÓN EN LENGUAJE NATURAL (AGENTE DE IA)\n"
    body += "=" * 64 + "\n"
    body += interpretation + "\n"
    if question_answer is not None:
        body += "\n" + "=" * 64 + "\n"
        body += f"[5] PREGUNTA DEL USUARIO\n{'=' * 64}\n"
        body += f"P: {args.pregunta}\n\nR: {question_answer}\n"

    _write_report(report_path, body, agent.mode, args.datos)

    print("\n" + "=" * 64)
    print("  PROCESO COMPLETADO")
    print(f"  - Grafo  : {png_path}")
    print(f"  - Reporte: {report_path}")
    print("=" * 64)
    return 0


def _write_report(
    path: Path, body: str, agent_mode: str, data_path: Path
) -> None:
    """Write the final report to disk with a metadata header."""
    header = (
        "ANÁLISIS ESTRUCTURAL DE REDES DE PROYECTOS — GRUPO 6\n"
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Datos   : {data_path}\n"
        f"Agente  : {agent_mode}\n"
        + "=" * 64
        + "\n\n"
    )
    path.write_text(header + body, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
