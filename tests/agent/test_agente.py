"""
Pruebas de agente_ia.py — agente híbrido.

Solo se prueba lo determinista y el MODO FALLBACK: estas pruebas NUNCA
llaman a la API de Claude. Para garantizarlo se fuerza una clave de
ejemplo con `monkeypatch.setenv` (load_dotenv no sobreescribe variables
ya presentes), de modo que `llm_disponible` es False y `interpretar` /
`responder` cortan antes de cualquier llamada de red.
"""

from pathlib import Path

import pytest

from project_network_analyzer.agent.agente_ia import MODELO_PREDETERMINADO, AgenteIA
from project_network_analyzer.domain.analizador import Analizador
from project_network_analyzer.domain.modelo import Red

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"


@pytest.fixture(autouse=True)
def _sin_clave_api(monkeypatch):
    """Fuerza modo fallback en todas las pruebas de este módulo."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "tu_clave_api_aqui")


@pytest.fixture
def contexto():
    red = Red.desde_json(DATOS)
    return red, red.validar(), Analizador(red).analizar()


# --------------------------------------------------------------------- #
# Configuración del modelo
# --------------------------------------------------------------------- #


def test_modelo_por_defecto_es_haiku():
    assert MODELO_PREDETERMINADO == "claude-haiku-4-5"
    assert AgenteIA().modelo == "claude-haiku-4-5"


def test_modelo_configurable():
    assert AgenteIA(modelo="claude-sonnet-4-6").modelo == "claude-sonnet-4-6"


# --------------------------------------------------------------------- #
# Estado en modo fallback
# --------------------------------------------------------------------- #


def test_modo_fallback_sin_clave_valida():
    agente = AgenteIA()
    assert agente.llm_disponible is False
    assert "fallback" in agente.modo


# --------------------------------------------------------------------- #
# Capa determinista (siempre disponible)
# --------------------------------------------------------------------- #


def test_reporte_estructurado_contiene_secciones(contexto):
    red, val, an = contexto
    reporte = AgenteIA().generar_reporte_estructurado(red, val, an)

    assert "VALIDACIÓN ESTRUCTURAL" in reporte
    assert "ANÁLISIS ESTRUCTURAL" in reporte
    assert "HALLAZGOS DETECTADOS POR REGLAS" in reporte
    assert "σ" in reporte
    assert red.nombre_proyecto in reporte


def test_reporte_detecta_patrones_clave(contexto):
    red, val, an = contexto
    reporte = AgenteIA().generar_reporte_estructurado(red, val, an)

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
    from project_network_analyzer.domain.analizador import ResultadoAnalisis

    vacio = ResultadoAnalisis(
        orden_topologico=[], caminos=[], numero_de_caminos=0,
        centralidad={}, nodos_criticos=[], sigma_maximo=0,
        cuellos_de_botella=[], puntos_articulacion=[],
        iniciales=[], finales=[], intermedias=[], generaciones=[],
    )
    reporte = AgenteIA().generar_reporte_estructurado(r, val, vacio)
    assert "INVÁLIDA" in reporte
    assert "ciclo" in reporte.lower()


# --------------------------------------------------------------------- #
# Capa LLM en fallback (sin llamadas de red)
# --------------------------------------------------------------------- #


def test_interpretar_en_fallback(contexto):
    red, val, an = contexto
    agente = AgenteIA()
    reporte = agente.generar_reporte_estructurado(red, val, an)
    salida = agente.interpretar(reporte)
    assert salida.startswith("[MODO FALLBACK")


def test_responder_en_fallback(contexto):
    red, val, an = contexto
    agente = AgenteIA()
    reporte = agente.generar_reporte_estructurado(red, val, an)
    salida = agente.responder("¿Cuál es el nodo más crítico?", reporte)
    assert salida.startswith("[MODO FALLBACK")
