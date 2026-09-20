"""
reporte.py — Capa determinista de reglas (Grupo 6).

Toma `ValidationResult` y `AnalysisResult` y genera un reporte
estructurado en texto, detectando patrones con reglas fijas (caminos
críticos, puntos de articulación, actividades paralelas...).

Es 100 % determinista y testeable: no hay I/O, ni red, ni clave API.
Este reporte es la salida completa del sistema por sí mismo, y también el
CONTEXTO que se entrega a la capa LLM (ver `agent/agente_ia.py`).

IMPORTANTE (condición del proyecto): toda la matemática vive en `domain/`.
Aquí solo se traducen números ya calculados a frases estructurales; el LLM
después las redacta, pero nunca las recalcula.
"""

from __future__ import annotations

from project_network_analyzer.domain.analysis import AnalysisResult
from project_network_analyzer.domain.network import Network, ValidationResult


def generar_reporte_estructurado(
    red: Network,
    validacion: ValidationResult,
    analisis: AnalysisResult,
) -> str:
    """
    Construye el reporte estructurado en texto a partir de los resultados
    del modelo. Es la salida determinista del sistema.
    """
    lineas: list[str] = []
    ad = lineas.append

    ad("=" * 64)
    ad(f"PROYECTO: {red.project_name}")
    if red.description:
        ad(red.description)
    ad(f"Actividades |V| = {len(red)}   Precedencias |E| = "
       f"{red.graph.number_of_edges()}")
    ad("=" * 64)

    ad("\n[1] VALIDACIÓN ESTRUCTURAL")
    ad(validacion.summary())

    ad("\n[2] ANÁLISIS ESTRUCTURAL")
    ad(analisis.summary())
    ad("\nCentralidad de paso σ(v) (caminos f→s que pasan por v):")
    for v, s in sorted(
        analisis.centrality.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        ad(f"  {v} ({red.name_of(v)}): σ = {s}")

    ad("\nClasificación de actividades:")
    ad(f"  Iniciales : {_con_nombres(red, analisis.initial)}")
    ad(f"  Finales   : {_con_nombres(red, analisis.final)}")
    ad(f"  Intermedias: {_con_nombres(red, analisis.intermediate)}")

    ad("\nFases (generaciones topológicas — actividades en paralelo):")
    for i, gen in enumerate(analisis.generations):
        marca = "  ← paralelas" if len(gen) > 1 else ""
        ad(f"  Fase {i}: {_con_nombres(red, gen)}{marca}")

    ad("\n[3] HALLAZGOS DETECTADOS POR REGLAS")
    for hallazgo in detectar_patrones(red, validacion, analisis):
        ad(f"  - {hallazgo}")

    return "\n".join(lineas)


def _con_nombres(red: Network, ids: list[str]) -> str:
    """Formatea 'A (nombre), B (nombre)' para legibilidad del reporte."""
    if not ids:
        return "(ninguna)"
    return ", ".join(f"{i} ({red.name_of(i)})" for i in ids)


def detectar_patrones(
    red: Network,
    validacion: ValidationResult,
    analisis: AnalysisResult,
) -> list[str]:
    """
    Reglas deterministas que traducen los números del análisis en
    afirmaciones estructurales. Estas frases son la materia prima que el
    LLM luego redacta en lenguaje natural.
    """
    h: list[str] = []

    if not validacion.is_valid:
        h.append(
            "La red NO es estructuralmente válida: no se cumple alguna "
            "restricción del modelo (ver sección [1])."
        )
        if validacion.detected_cycle:
            h.append(
                "Se detectó un ciclo dirigido: "
                f"{' → '.join(validacion.detected_cycle)}. Un proyecto "
                "no puede tener dependencias circulares."
            )

    n = analisis.path_count
    if n > 1:
        h.append(
            f"Existen {n} caminos estructurales distintos de la fuente al "
            "sumidero: el proyecto admite múltiples secuencias de ejecución."
        )
    elif n == 1:
        h.append(
            "Existe un único camino fuente→sumidero: la red es una cadena "
            "sin alternativas estructurales."
        )

    for v in analisis.articulation_points:
        h.append(
            f"El nodo {v} ({red.name_of(v)}) es un PUNTO DE ARTICULACIÓN: "
            "su eliminación desconectaría la red. Es un cuello de botella "
            "estructural crítico; conviene mitigar su riesgo."
        )

    cuellos_no_art = [
        c for c in analisis.bottlenecks
        if c not in analisis.articulation_points
    ]
    if cuellos_no_art:
        h.append(
            "Pasan TODOS los caminos por: "
            f"{', '.join(cuellos_no_art)}. Son obligatorios en cualquier "
            "ejecución (aunque no desconectan la red)."
        )

    if analisis.critical_nodes:
        h.append(
            f"Nodos críticos V* = {{{', '.join(analisis.critical_nodes)}}} "
            f"con σ máximo = {analisis.max_sigma}: concentran el mayor "
            "paso de caminos y son los más sensibles estructuralmente."
        )

    # Paralelismo en la primera fase con más de una actividad.
    for i, gen in enumerate(analisis.generations):
        if len(gen) > 1:
            h.append(
                f"En la fase {i} hay {len(gen)} actividades que pueden "
                f"ejecutarse en paralelo: {', '.join(gen)}."
            )
            break

    total_paralelas = sum(
        1 for g in analisis.generations if len(g) > 1
    )
    if total_paralelas:
        h.append(
            f"Hay {total_paralelas} fase(s) con paralelismo estructural: "
            "permiten acortar la ruta del proyecto si hay recursos."
        )

    return h
