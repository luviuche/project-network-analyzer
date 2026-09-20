"""
Pruebas de services/reporte.py — capa determinista de reglas.

Estas pruebas no tocan la capa LLM en absoluto: el reporte estructurado
se construye sin cliente, sin clave API y sin red. Por eso aquí no hace
falta forzar el modo fallback como en las pruebas del agente.
"""

from pathlib import Path

import pytest

from project_network_analyzer.domain.analysis import AnalysisResult, StructuralAnalyzer
from project_network_analyzer.domain.network import Network
from project_network_analyzer.infrastructure.cargador import cargar_red
from project_network_analyzer.services.reporte import generar_reporte_estructurado

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"


@pytest.fixture
def contexto():
    red = cargar_red(DATOS)
    return red, red.validate(), StructuralAnalyzer(red).analyze()


def test_reporte_estructurado_contiene_secciones(contexto):
    red, val, an = contexto
    reporte = generar_reporte_estructurado(red, val, an)

    assert "VALIDACIÓN ESTRUCTURAL" in reporte
    assert "ANÁLISIS ESTRUCTURAL" in reporte
    assert "HALLAZGOS DETECTADOS POR REGLAS" in reporte
    assert "σ" in reporte
    assert red.project_name in reporte


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
    r = Network("ciclica")
    for n in ("X", "Y"):
        r.add_activity(n, n)
    r.add_precedence("X", "Y")
    r.add_precedence("Y", "X")
    val = r.validate()

    # Análisis no disponible (no es DAG): se pasa un análisis "vacío"
    # solo para comprobar que el reporte de validación se genera igual.
    vacio = AnalysisResult(
        topological_order=[], paths=[], path_count=0,
        centrality={}, critical_nodes=[], max_sigma=0,
        bottlenecks=[], articulation_points=[],
        initial=[], final=[], intermediate=[], generations=[],
    )
    reporte = generar_reporte_estructurado(r, val, vacio)
    assert "INVÁLIDA" in reporte
    assert "ciclo" in reporte.lower()
