"""
cli.py — The project orchestrator.

Chains the whole flow together:

    JSON  →  Network (domain)  →  validation  →  structural analysis
          →  rendering (PNG)   →  hybrid agent  →  report.txt

Run it with:

    pna

Optionally:

    pna --data data/other.json --question "...?" --model claude-sonnet-5

The mathematics lives in `domain/`; the agent only interprets. This
module computes nothing: it only coordinates.
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
DEFAULT_DATA_FILE = ROOT / "data" / "software_project.json"
OUTPUT_DIR = ROOT / "outputs"


def _parse_args() -> argparse.Namespace:
    """Define and parse the command-line arguments."""
    p = argparse.ArgumentParser(
        description="Structural analysis of a project network."
    )
    p.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Path to the project JSON (default: data/software_project.json).",
    )
    p.add_argument(
        "--question",
        type=str,
        default=None,
        help="Open question for the agent about the network (optional).",
    )
    p.add_argument(
        "--model",
        type=str,
        default=None,
        help="Claude model for the LLM layer (optional, e.g. "
        "claude-sonnet-5). Defaults to the configured one.",
    )
    return p.parse_args()


def _step(number: int, text: str) -> None:
    """Print a step marker on the console."""
    print(f"\n[{number}] {text}")


def main() -> int:
    """Run the whole flow. Returns the process exit code."""
    args = _parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    png_path = OUTPUT_DIR / "network_graph.png"
    report_path = OUTPUT_DIR / "report.txt"

    print("=" * 64)
    print("  STRUCTURAL ANALYSIS OF PROJECT NETWORKS")
    print("=" * 64)

    # ---- 1. Load the network ----------------------------------------- #
    _step(1, f"Loading the network from: {args.data}")
    try:
        network = load_network(args.data)
    except NetworkStructureError as e:
        print(f"  ERROR building the network: {e}", file=sys.stderr)
        return 1
    print(f"  OK — {network!r}")

    # ---- 2. Structural validation ------------------------------------ #
    _step(2, "Validating the model's constraints")
    validation = network.validate()
    print(validation.summary())

    # ---- 3. Agent: created early so an invalid network still gets a
    #        deterministic report explaining the problem --------------- #
    agent = LLMAgent(model=args.model)
    print(f"\n  Agent mode: {agent.mode}")

    if not validation.is_valid:
        _step(3, "The network is NOT valid: skipping the structural analysis")
        print("  (Path and centrality analysis requires a valid DAG.)")
        body = (
            f"PROJECT: {network.project_name}\n"
            f"{'=' * 64}\n\n"
            "[1] STRUCTURAL VALIDATION\n"
            f"{validation.summary()}\n\n"
            "The network breaks at least one of the model's constraints, so "
            "neither the structural analysis nor the rendering is run.\n"
        )
        _write_report(report_path, body, agent.mode, args.data)
        print(f"\n  Partial report written to: {report_path}")
        return 1

    # ---- 4. Structural analysis -------------------------------------- #
    _step(4, "Running the structural analysis")
    analysis = StructuralAnalyzer(network).analyze()
    print(analysis.summary())

    # ---- 5. Rendering -------------------------------------------------#
    _step(5, "Rendering the graph")
    GraphRenderer(network, analysis).render(png_path)
    print(f"  OK — graph saved to: {png_path}")

    # ---- 6. Structured report + LLM interpretation ------------------- #
    _step(6, "Building the structured report (deterministic layer)")
    structured_report = build_structured_report(network, validation, analysis)
    print("  OK — structured report built.")

    _step(7, "Interpreting the report (LLM layer or fallback)")
    interpretation = agent.interpret(structured_report)
    print("  OK — interpretation received.")

    question_answer = None
    if args.question:
        _step(8, f"Answering the question: \"{args.question}\"")
        question_answer = agent.answer(args.question, structured_report)
        print("  OK — answer received.")

    # ---- 7. Write the final report ----------------------------------- #
    body = structured_report + "\n\n"
    body += "=" * 64 + "\n"
    body += "[4] NATURAL-LANGUAGE INTERPRETATION (AI AGENT)\n"
    body += "=" * 64 + "\n"
    body += interpretation + "\n"
    if question_answer is not None:
        body += "\n" + "=" * 64 + "\n"
        body += f"[5] USER QUESTION\n{'=' * 64}\n"
        body += f"Q: {args.question}\n\nA: {question_answer}\n"

    _write_report(report_path, body, agent.mode, args.data)

    print("\n" + "=" * 64)
    print("  DONE")
    print(f"  - Graph : {png_path}")
    print(f"  - Report: {report_path}")
    print("=" * 64)
    return 0


def _write_report(
    path: Path, body: str, agent_mode: str, data_path: Path
) -> None:
    """Write the final report to disk with a metadata header."""
    header = (
        "STRUCTURAL ANALYSIS OF PROJECT NETWORKS\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Data     : {data_path}\n"
        f"Agent    : {agent_mode}\n"
        + "=" * 64
        + "\n\n"
    )
    path.write_text(header + body, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
