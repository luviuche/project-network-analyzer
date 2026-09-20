"""
Tests for agent/llm_agent.py — the LLM layer of the hybrid agent.

Only configuration and FALLBACK MODE are tested: these tests NEVER call
the Claude API. To guarantee that, a placeholder key is forced with
`monkeypatch.setenv` (load_dotenv does not override variables that are
already set), so `llm_available` is False and `interpret` / `answer`
return before any network call.

The rule layer is tested separately, in `tests/services/test_report.py`.
"""

import sys
from pathlib import Path

import pytest

from project_network_analyzer.agent.llm_agent import DEFAULT_MODEL, LLMAgent
from project_network_analyzer.domain.analysis import StructuralAnalyzer
from project_network_analyzer.infrastructure.loader import load_network
from project_network_analyzer.services.report import build_structured_report

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "proyecto_software.json"


@pytest.fixture(autouse=True)
def _without_api_key(monkeypatch):
    """Force fallback mode for every test in this module."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "tu_clave_api_aqui")


@pytest.fixture
def report():
    """A real structured report, built without touching the LLM layer."""
    network = load_network(DATA_FILE)
    return build_structured_report(
        network, network.validate(), StructuralAnalyzer(network).analyze()
    )


# --------------------------------------------------------------------- #
# Model configuration
# --------------------------------------------------------------------- #


def test_default_model_is_haiku():
    assert DEFAULT_MODEL == "claude-haiku-4-5"
    assert LLMAgent().model == "claude-haiku-4-5"


def test_model_is_configurable():
    assert LLMAgent(model="claude-sonnet-5").model == "claude-sonnet-5"


# --------------------------------------------------------------------- #
# State in fallback mode
# --------------------------------------------------------------------- #


def test_fallback_mode_without_a_valid_key():
    agent = LLMAgent()
    assert agent.llm_available is False
    assert "fallback" in agent.mode


# --------------------------------------------------------------------- #
# The LLM layer in fallback (no network calls)
# --------------------------------------------------------------------- #


def test_interpret_in_fallback(report):
    output = LLMAgent().interpret(report)
    assert output.startswith("[MODO FALLBACK")


def test_answer_in_fallback(report):
    output = LLMAgent().answer("¿Cuál es el nodo más crítico?", report)
    assert output.startswith("[MODO FALLBACK")


def test_fallback_when_the_sdk_is_not_installed(monkeypatch, report):
    """
    With a valid key but no `anthropic` package, the agent must fall back
    to the notice and NOT raise.

    Regression: the `import anthropic` used to sit inside the same `try`
    as the `except anthropic.X` handlers, so with the package missing
    Python tried to evaluate `anthropic.AuthenticationError` against an
    unbound name and an `UnboundLocalError` escaped to the user.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-valida-de-prueba")
    # None in sys.modules makes `import anthropic` raise
    # ModuleNotFoundError without uninstalling anything.
    monkeypatch.setitem(sys.modules, "anthropic", None)

    agent = LLMAgent()
    assert agent.llm_available is True  # the key guard does not intervene

    output = agent.interpret(report)
    assert output.startswith("[MODO FALLBACK")
    assert "anthropic" in output
