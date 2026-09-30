"""
prompts.py — Prompts for the LLM layer.

The prompts live here rather than inline in the agent logic, so they can
be reviewed, versioned and tuned without touching the call flow.

The contract they impose is the project's own: the model INTERPRETS the
structured report, it never recomputes it.
"""

from __future__ import annotations

SYSTEM = (
    "You are an Operations Research assistant specialised in the "
    "STRUCTURAL ANALYSIS of project networks (directed acyclic graphs).\n\n"
    "You are given a STRUCTURED REPORT already computed by a "
    "deterministic mathematical model. Your ONLY task is to interpret it: "
    "explain it in clear natural language, answer questions and suggest "
    "structural improvements.\n\n"
    "STRICT RULES:\n"
    "- NEVER recompute or invent numbers: use only those in the report.\n"
    "- If a piece of data is not in the report, say so explicitly.\n"
    "- Do not discuss duration, cost or resources: the scope is STRUCTURAL.\n"
    "- Answer in English, technically precise but accessible."
)

INTERPRET_INSTRUCTION = (
    "Write an interpretation of the structured report with this "
    "structure:\n"
    "1) Executive summary (3-4 sentences).\n"
    "2) Reading of the critical nodes and articulation points: what they "
    "imply for planning the project.\n"
    "3) Reading of the parallelism between activities.\n"
    "4) Suggestions to improve the network's STRUCTURE "
    "(without discussing time or cost)."
)


def report_context(structured_report: str) -> str:
    """Wrap the report as a context block: the single source of truth."""
    return (
        "STRUCTURED REPORT (single source of truth):\n\n"
        + structured_report
    )


def answer_instruction(question: str) -> str:
    """Instruction for an open user question about the network."""
    return (
        "User question about this project's network:\n"
        f"\"{question}\"\n\n"
        "Answer relying EXCLUSIVELY on the structured report. "
        "If the answer cannot be deduced from the report, say so clearly."
    )
