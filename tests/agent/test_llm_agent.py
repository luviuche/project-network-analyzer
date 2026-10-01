"""
Tests for agent/llm_agent.py — the LLM layer of the hybrid agent.

Configuration and FALLBACK MODE are tested, plus how a model reply is
marked, through a stand-in client: these tests NEVER call the Claude API. To guarantee that, a placeholder key is forced with
`monkeypatch.setenv` (load_dotenv does not override variables that are
already set), so `llm_available` is False and `interpret` / `answer`
return before any network call.

The rule layer is tested separately, in `tests/services/test_report.py`.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from project_network_analyzer.agent.llm_agent import AgentReply, LLMAgent
from project_network_analyzer.config import DEFAULT_MODEL
from project_network_analyzer.domain.analysis import StructuralAnalyzer
from project_network_analyzer.infrastructure.loader import load_network
from project_network_analyzer.services.report import build_structured_report

ROOT = Path(__file__).resolve().parents[2]
DATA_FILE = ROOT / "data" / "software_project.json"


@pytest.fixture(autouse=True)
def _without_api_key(monkeypatch):
    """Force fallback mode for every test in this module."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "your_api_key_here")


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
    assert DEFAULT_MODEL == "claude-haiku-4-5-20251001"
    assert LLMAgent().model == DEFAULT_MODEL


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
    reply = LLMAgent().interpret(report)
    assert reply.from_llm is False
    assert reply.text.startswith("[FALLBACK MODE")


def test_answer_in_fallback(report):
    reply = LLMAgent().answer("Which node is the most critical?", report)
    assert reply.from_llm is False
    assert reply.text.startswith("[FALLBACK MODE")


def test_fallback_when_the_sdk_is_not_installed(monkeypatch, report):
    """
    With a valid key but no `anthropic` package, the agent must fall back
    to the notice and NOT raise.

    Regression: the `import anthropic` used to sit inside the same `try`
    as the `except anthropic.X` handlers, so with the package missing
    Python tried to evaluate `anthropic.AuthenticationError` against an
    unbound name and an `UnboundLocalError` escaped to the user.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-valid-test-key")
    # None in sys.modules makes `import anthropic` raise
    # ModuleNotFoundError without uninstalling anything.
    monkeypatch.setitem(sys.modules, "anthropic", None)

    agent = LLMAgent()
    assert agent.llm_available is True  # the key guard does not intervene

    reply = agent.interpret(report)
    assert reply.from_llm is False
    assert reply.text.startswith("[FALLBACK MODE")
    assert "anthropic" in reply.text


# --------------------------------------------------------------------- #
# A model reply (a stand-in client: still no network calls)
# --------------------------------------------------------------------- #


class _FakeClient:
    """Answers `messages.create` with fixed text blocks."""

    def __init__(self, *texts: str) -> None:
        blocks = [SimpleNamespace(type="text", text=text) for text in texts]
        self.messages = SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(content=blocks)
        )


@pytest.fixture
def agent_with_reply(monkeypatch):
    """An agent with a usable key whose client returns the given text."""
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-valid-test-key")

    def build(*texts: str) -> LLMAgent:
        agent = LLMAgent()
        agent._client = _FakeClient(*texts)
        return agent

    return build


def test_a_model_reply_is_marked_as_from_the_llm(agent_with_reply, report):
    reply = agent_with_reply("The network ", "funnels through B.").answer(
        "Which node is the most critical?", report
    )
    assert reply == AgentReply(text="The network \nfunnels through B.", from_llm=True)


def test_an_empty_model_reply_falls_back(agent_with_reply, report):
    reply = agent_with_reply("   ").interpret(report)
    assert reply.from_llm is False
    assert "returned no text" in reply.text
