"""
Pruebas de agent/agente_ia.py — capa LLM del agente híbrido.

Solo se prueba la configuración y el MODO FALLBACK: estas pruebas NUNCA
llaman a la API de Claude. Para garantizarlo se fuerza una clave de
ejemplo con `monkeypatch.setenv` (load_dotenv no sobreescribe variables
ya presentes), de modo que `llm_disponible` es False y `interpretar` /
`responder` cortan antes de cualquier llamada de red.

La capa determinista se prueba aparte, en `tests/services/test_reporte.py`.
"""

import sys
from pathlib import Path

import pytest

from project_network_analyzer.agent.agente_ia import MODELO_PREDETERMINADO, AgenteIA
from project_network_analyzer.domain.analysis import StructuralAnalyzer
from project_network_analyzer.infrastructure.cargador import cargar_red
from project_network_analyzer.services.report import build_structured_report

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"


@pytest.fixture(autouse=True)
def _sin_clave_api(monkeypatch):
    """Fuerza modo fallback en todas las pruebas de este módulo."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "tu_clave_api_aqui")


@pytest.fixture
def reporte():
    """Reporte estructurado real, construido sin tocar la capa LLM."""
    red = cargar_red(DATOS)
    return build_structured_report(
        red, red.validate(), StructuralAnalyzer(red).analyze()
    )


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
# Capa LLM en fallback (sin llamadas de red)
# --------------------------------------------------------------------- #


def test_interpretar_en_fallback(reporte):
    salida = AgenteIA().interpretar(reporte)
    assert salida.startswith("[MODO FALLBACK")


def test_responder_en_fallback(reporte):
    salida = AgenteIA().responder("¿Cuál es el nodo más crítico?", reporte)
    assert salida.startswith("[MODO FALLBACK")


def test_fallback_si_el_sdk_no_esta_instalado(monkeypatch, reporte):
    """
    Con clave válida pero sin el paquete `anthropic`, el agente debe caer
    al aviso de fallback y NO lanzar.

    Regresión: el `import anthropic` vivía dentro del mismo `try` que los
    `except anthropic.X`, así que al faltar el paquete Python intentaba
    evaluar `anthropic.AuthenticationError` con el nombre sin asignar y
    escapaba un `UnboundLocalError` hasta el usuario.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-valida-de-prueba")
    # None en sys.modules hace que `import anthropic` lance
    # ModuleNotFoundError sin tener que desinstalar nada.
    monkeypatch.setitem(sys.modules, "anthropic", None)

    agente = AgenteIA()
    assert agente.llm_disponible is True  # el guard de clave no interviene

    salida = agente.interpretar(reporte)
    assert salida.startswith("[MODO FALLBACK")
    assert "anthropic" in salida
