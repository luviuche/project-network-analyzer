"""
prompts.py — Prompts for the LLM layer.

The prompts live here rather than inline in the agent logic, so they can
be reviewed, versioned and tuned without touching the call flow.

The contract they impose is the project's own: the model INTERPRETS the
structured report, it never recomputes it.

The prompt text is Spanish because the model answers the user in
Spanish; the identifiers and docstrings around it are English.
"""

from __future__ import annotations

SYSTEM = (
    "Eres un asistente experto en Investigación de Operaciones, "
    "especializado en el ANÁLISIS ESTRUCTURAL de redes de proyectos "
    "(grafos dirigidos acíclicos). Trabajas para un proyecto "
    "universitario del Grupo 6.\n\n"
    "Se te entrega un REPORTE ESTRUCTURADO ya calculado por un modelo "
    "matemático determinista. Tu tarea es ÚNICAMENTE interpretarlo: "
    "explicarlo en lenguaje natural claro, responder preguntas y "
    "sugerir mejoras estructurales.\n\n"
    "REGLAS ESTRICTAS:\n"
    "- NUNCA recalcules ni inventes números: usa solo los del reporte.\n"
    "- Si un dato no está en el reporte, dilo explícitamente.\n"
    "- No trates duración, costos ni recursos: el alcance es ESTRUCTURAL.\n"
    "- Responde en español, con precisión técnica pero accesible."
)

INTERPRET_INSTRUCTION = (
    "Redacta una interpretación del reporte estructurado para el "
    "informe del proyecto, con esta estructura:\n"
    "1) Resumen ejecutivo (3-4 frases).\n"
    "2) Lectura de los nodos críticos y puntos de articulación: qué "
    "implican para la planeación del proyecto de software.\n"
    "3) Lectura del paralelismo entre actividades.\n"
    "4) Sugerencias para mejorar la ESTRUCTURA de la red "
    "(sin hablar de tiempos ni costos)."
)


def report_context(structured_report: str) -> str:
    """Wrap the report as a context block: the single source of truth."""
    return (
        "REPORTE ESTRUCTURADO (fuente única de verdad):\n\n"
        + structured_report
    )


def answer_instruction(question: str) -> str:
    """Instruction for an open user question about the network."""
    return (
        "Pregunta del usuario sobre la red de este proyecto:\n"
        f"«{question}»\n\n"
        "Responde apoyándote EXCLUSIVAMENTE en el reporte estructurado. "
        "Si la respuesta no se puede deducir del reporte, dilo claramente."
    )
