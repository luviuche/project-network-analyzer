"""
cli.py — Orquestador del proyecto (Grupo 6).

Encadena todo el flujo del sistema:

    JSON  →  Red (modelo)  →  validación  →  análisis estructural
          →  visualización (PNG)  →  agente híbrido  →  reporte.txt

Se ejecuta con:

    PYTHONPATH=src python -m project_network_analyzer.cli

Opcionalmente:

    PYTHONPATH=src python -m project_network_analyzer.cli \
        --datos data/otro.json --pregunta "¿...?" --modelo claude-sonnet-5

La matemática vive en `domain/`; el agente solo interpreta. Este módulo
no calcula nada: únicamente coordina.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from project_network_analyzer.agent.agente_ia import AgenteIA
from project_network_analyzer.domain.analizador import Analizador
from project_network_analyzer.domain.modelo import ErrorEstructuraRed, Red
from project_network_analyzer.infrastructure.visualizador import Visualizador
from project_network_analyzer.services.reporte import generar_reporte_estructurado

# Raíz del proyecto = src/project_network_analyzer/ -> src/ -> raíz. Hace
# que el script funcione sin importar desde qué directorio se invoque.
RAIZ = Path(__file__).resolve().parents[2]
DATOS_POR_DEFECTO = RAIZ / "data" / "proyecto_software.json"
DIR_SALIDA = RAIZ / "outputs"


def _argumentos() -> argparse.Namespace:
    """Define y parsea los argumentos de línea de comandos."""
    p = argparse.ArgumentParser(
        description="Análisis estructural de una red de proyecto (Grupo 6)."
    )
    p.add_argument(
        "--datos",
        type=Path,
        default=DATOS_POR_DEFECTO,
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
        "claude-sonnet-4-6). Por defecto usa el del agente.",
    )
    return p.parse_args()


def _paso(numero: int, texto: str) -> None:
    """Imprime un marcador de paso en consola."""
    print(f"\n[{numero}] {texto}")


def main() -> int:
    """Ejecuta el flujo completo. Devuelve el código de salida del proceso."""
    args = _argumentos()
    DIR_SALIDA.mkdir(parents=True, exist_ok=True)
    ruta_png = DIR_SALIDA / "grafo_red.png"
    ruta_reporte = DIR_SALIDA / "reporte.txt"

    print("=" * 64)
    print("  ANÁLISIS ESTRUCTURAL DE REDES DE PROYECTOS — GRUPO 6")
    print("=" * 64)

    # ---- 1. Cargar la red -------------------------------------------- #
    _paso(1, f"Cargando la red desde: {args.datos}")
    try:
        red = Red.desde_json(args.datos)
    except ErrorEstructuraRed as e:
        print(f"  ERROR al construir la red: {e}", file=sys.stderr)
        return 1
    print(f"  OK — {red!r}")

    # ---- 2. Validación estructural ----------------------------------- #
    _paso(2, "Validando las restricciones del modelo")
    validacion = red.validar()
    print(validacion.resumen())

    # ---- 3. Agente: capa determinista (siempre disponible) ----------- #
    # Se crea ya el agente; si la red es inválida, igual emitimos el
    # reporte determinista explicando el problema (nunca queda inoperante).
    agente = AgenteIA(modelo=args.modelo)
    print(f"\n  Agente en modo: {agente.modo}")

    if not validacion.es_valida:
        _paso(3, "La red NO es válida: se omite el análisis estructural")
        print("  (El análisis de caminos/centralidad requiere un DAG válido.)")
        cuerpo = (
            f"PROYECTO: {red.nombre_proyecto}\n"
            f"{'=' * 64}\n\n"
            "[1] VALIDACIÓN ESTRUCTURAL\n"
            f"{validacion.resumen()}\n\n"
            "La red no cumple alguna restricción del modelo, por lo que no "
            "se ejecuta el análisis estructural ni la visualización.\n"
        )
        _escribir_reporte(ruta_reporte, cuerpo, agente.modo, args.datos)
        print(f"\n  Reporte (parcial) escrito en: {ruta_reporte}")
        return 1

    # ---- 4. Análisis estructural ------------------------------------- #
    _paso(4, "Ejecutando el análisis estructural")
    analisis = Analizador(red).analizar()
    print(analisis.resumen())

    # ---- 5. Visualización -------------------------------------------- #
    _paso(5, "Generando la visualización del grafo")
    Visualizador(red, analisis).generar(ruta_png)
    print(f"  OK — grafo guardado en: {ruta_png}")

    # ---- 6. Agente: reporte estructurado + interpretación LLM -------- #
    _paso(6, "Construyendo el reporte estructurado (capa determinista)")
    reporte_estructurado = generar_reporte_estructurado(
        red, validacion, analisis
    )
    print("  OK — reporte estructurado generado.")

    _paso(7, "Interpretando el reporte (capa LLM o fallback)")
    interpretacion = agente.interpretar(reporte_estructurado)
    print("  OK — interpretación obtenida.")

    respuesta_pregunta = None
    if args.pregunta:
        _paso(8, f"Respondiendo la pregunta: «{args.pregunta}»")
        respuesta_pregunta = agente.responder(
            args.pregunta, reporte_estructurado
        )
        print("  OK — respuesta obtenida.")

    # ---- 7. Escribir el reporte final -------------------------------- #
    cuerpo = reporte_estructurado + "\n\n"
    cuerpo += "=" * 64 + "\n"
    cuerpo += "[4] INTERPRETACIÓN EN LENGUAJE NATURAL (AGENTE DE IA)\n"
    cuerpo += "=" * 64 + "\n"
    cuerpo += interpretacion + "\n"
    if respuesta_pregunta is not None:
        cuerpo += "\n" + "=" * 64 + "\n"
        cuerpo += f"[5] PREGUNTA DEL USUARIO\n{'=' * 64}\n"
        cuerpo += f"P: {args.pregunta}\n\nR: {respuesta_pregunta}\n"

    _escribir_reporte(ruta_reporte, cuerpo, agente.modo, args.datos)

    print("\n" + "=" * 64)
    print("  PROCESO COMPLETADO")
    print(f"  - Grafo  : {ruta_png}")
    print(f"  - Reporte: {ruta_reporte}")
    print("=" * 64)
    return 0


def _escribir_reporte(
    ruta: Path, cuerpo: str, modo_agente: str, ruta_datos: Path
) -> None:
    """Escribe el reporte final en disco con una cabecera de metadatos."""
    cabecera = (
        "ANÁLISIS ESTRUCTURAL DE REDES DE PROYECTOS — GRUPO 6\n"
        f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Datos   : {ruta_datos}\n"
        f"Agente  : {modo_agente}\n"
        + "=" * 64
        + "\n\n"
    )
    ruta.write_text(cabecera + cuerpo, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
