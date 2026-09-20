"""
reporte.py — Capa determinista de reglas (Grupo 6).

Toma `ResultadoValidacion` y `ResultadoAnalisis` y genera un reporte
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

from project_network_analyzer.domain.analizador import ResultadoAnalisis
from project_network_analyzer.domain.modelo import Red, ResultadoValidacion


def generar_reporte_estructurado(
    red: Red,
    validacion: ResultadoValidacion,
    analisis: ResultadoAnalisis,
) -> str:
    """
    Construye el reporte estructurado en texto a partir de los resultados
    del modelo. Es la salida determinista del sistema.
    """
    lineas: list[str] = []
    ad = lineas.append

    ad("=" * 64)
    ad(f"PROYECTO: {red.nombre_proyecto}")
    if red.descripcion:
        ad(red.descripcion)
    ad(f"Actividades |V| = {len(red)}   Precedencias |E| = "
       f"{red.grafo.number_of_edges()}")
    ad("=" * 64)

    ad("\n[1] VALIDACIÓN ESTRUCTURAL")
    ad(validacion.resumen())

    ad("\n[2] ANÁLISIS ESTRUCTURAL")
    ad(analisis.resumen())
    ad("\nCentralidad de paso σ(v) (caminos f→s que pasan por v):")
    for v, s in sorted(
        analisis.centralidad.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        ad(f"  {v} ({red.nombre_de(v)}): σ = {s}")

    ad("\nClasificación de actividades:")
    ad(f"  Iniciales : {_con_nombres(red, analisis.iniciales)}")
    ad(f"  Finales   : {_con_nombres(red, analisis.finales)}")
    ad(f"  Intermedias: {_con_nombres(red, analisis.intermedias)}")

    ad("\nFases (generaciones topológicas — actividades en paralelo):")
    for i, gen in enumerate(analisis.generaciones):
        marca = "  ← paralelas" if len(gen) > 1 else ""
        ad(f"  Fase {i}: {_con_nombres(red, gen)}{marca}")

    ad("\n[3] HALLAZGOS DETECTADOS POR REGLAS")
    for hallazgo in detectar_patrones(red, validacion, analisis):
        ad(f"  - {hallazgo}")

    return "\n".join(lineas)


def _con_nombres(red: Red, ids: list[str]) -> str:
    """Formatea 'A (nombre), B (nombre)' para legibilidad del reporte."""
    if not ids:
        return "(ninguna)"
    return ", ".join(f"{i} ({red.nombre_de(i)})" for i in ids)


def detectar_patrones(
    red: Red,
    validacion: ResultadoValidacion,
    analisis: ResultadoAnalisis,
) -> list[str]:
    """
    Reglas deterministas que traducen los números del análisis en
    afirmaciones estructurales. Estas frases son la materia prima que el
    LLM luego redacta en lenguaje natural.
    """
    h: list[str] = []

    if not validacion.es_valida:
        h.append(
            "La red NO es estructuralmente válida: no se cumple alguna "
            "restricción del modelo (ver sección [1])."
        )
        if validacion.ciclo_detectado:
            h.append(
                "Se detectó un ciclo dirigido: "
                f"{' → '.join(validacion.ciclo_detectado)}. Un proyecto "
                "no puede tener dependencias circulares."
            )

    n = analisis.numero_de_caminos
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

    for v in analisis.puntos_articulacion:
        h.append(
            f"El nodo {v} ({red.nombre_de(v)}) es un PUNTO DE ARTICULACIÓN: "
            "su eliminación desconectaría la red. Es un cuello de botella "
            "estructural crítico; conviene mitigar su riesgo."
        )

    cuellos_no_art = [
        c for c in analisis.cuellos_de_botella
        if c not in analisis.puntos_articulacion
    ]
    if cuellos_no_art:
        h.append(
            "Pasan TODOS los caminos por: "
            f"{', '.join(cuellos_no_art)}. Son obligatorios en cualquier "
            "ejecución (aunque no desconectan la red)."
        )

    if analisis.nodos_criticos:
        h.append(
            f"Nodos críticos V* = {{{', '.join(analisis.nodos_criticos)}}} "
            f"con σ máximo = {analisis.sigma_maximo}: concentran el mayor "
            "paso de caminos y son los más sensibles estructuralmente."
        )

    # Paralelismo en la primera fase con más de una actividad.
    for i, gen in enumerate(analisis.generaciones):
        if len(gen) > 1:
            h.append(
                f"En la fase {i} hay {len(gen)} actividades que pueden "
                f"ejecutarse en paralelo: {', '.join(gen)}."
            )
            break

    total_paralelas = sum(
        1 for g in analisis.generaciones if len(g) > 1
    )
    if total_paralelas:
        h.append(
            f"Hay {total_paralelas} fase(s) con paralelismo estructural: "
            "permiten acortar la ruta del proyecto si hay recursos."
        )

    return h
