"""
Pruebas de services/reporte.py — capa determinista de reglas.

Estas pruebas no tocan la capa LLM en absoluto: el reporte estructurado
se construye sin cliente, sin clave API y sin red. Por eso aquí no hace
falta forzar el modo fallback como en las pruebas del agente.
"""

from pathlib import Path

import pytest

from project_network_analyzer.domain.analizador import Analizador, ResultadoAnalisis
from project_network_analyzer.domain.modelo import Red
from project_network_analyzer.infrastructure.cargador import cargar_red
from project_network_analyzer.services.reporte import generar_reporte_estructurado

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"


@pytest.fixture
def contexto():
    red = cargar_red(DATOS)
    return red, red.validar(), Analizador(red).analizar()


def test_reporte_estructurado_contiene_secciones(contexto):
    red, val, an = contexto
    reporte = generar_reporte_estructurado(red, val, an)

    assert "VALIDACIÓN ESTRUCTURAL" in reporte
    assert "ANÁLISIS ESTRUCTURAL" in reporte
    assert "HALLAZGOS DETECTADOS POR REGLAS" in reporte
    assert "σ" in reporte
    assert red.nombre_proyecto in reporte


def test_reporte_detecta_patrones_clave(contexto):
    red, val, an = contexto
    reporte = generar_reporte_estructurado(red, val, an)

    assert "12 caminos" in reporte
    assert "PUNTO DE ARTICULACIÓN" in reporte
    assert "B (" in reporte and "N (" in reporte           # B y N articulación
    assert "V* = {A, B, N, O}" in reporte
    assert "paralelo" in reporte


def test_reporte_funciona_con_red_invalida():
    """La capa determinista debe explicar el problema, no romperse."""
    r = Red("ciclica")
    for n in ("X", "Y"):
        r.agregar_actividad(n, n)
    r.agregar_precedencia("X", "Y")
    r.agregar_precedencia("Y", "X")
    val = r.validar()

    # Análisis no disponible (no es DAG): se pasa un análisis "vacío"
    # solo para comprobar que el reporte de validación se genera igual.
    vacio = ResultadoAnalisis(
        orden_topologico=[], caminos=[], numero_de_caminos=0,
        centralidad={}, nodos_criticos=[], sigma_maximo=0,
        cuellos_de_botella=[], puntos_articulacion=[],
        iniciales=[], finales=[], intermedias=[], generaciones=[],
    )
    reporte = generar_reporte_estructurado(r, val, vacio)
    assert "INVÁLIDA" in reporte
    assert "ciclo" in reporte.lower()
