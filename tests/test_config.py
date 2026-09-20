"""
Tests for config.py — resolving the LLM layer's configuration.

Every test sets the environment explicitly, so none of them depends on
whether a real `.env` exists on the machine running them.
"""

import pytest

from project_network_analyzer.config import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    load_settings,
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    """Start from a known environment: no key, no overrides."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "tu_clave_api_aqui")
    monkeypatch.delenv("PNA_MODEL", raising=False)
    monkeypatch.delenv("PNA_MAX_TOKENS", raising=False)


def test_defaults_when_nothing_is_set():
    settings = load_settings()
    assert settings.model == DEFAULT_MODEL
    assert settings.max_tokens == DEFAULT_MAX_TOKENS


def test_environment_overrides_the_defaults(monkeypatch):
    monkeypatch.setenv("PNA_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("PNA_MAX_TOKENS", "1234")

    settings = load_settings()
    assert settings.model == "claude-sonnet-5"
    assert settings.max_tokens == 1234


def test_explicit_arguments_win_over_the_environment(monkeypatch):
    monkeypatch.setenv("PNA_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("PNA_MAX_TOKENS", "1234")

    settings = load_settings(model="claude-haiku-4-5", max_tokens=99)
    assert settings.model == "claude-haiku-4-5"
    assert settings.max_tokens == 99


def test_placeholder_key_is_not_usable():
    assert load_settings().api_key_is_usable is False


def test_real_looking_key_is_usable(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-clave-de-prueba")
    assert load_settings().api_key_is_usable is True


@pytest.mark.parametrize("raw", ["no-soy-un-entero", "0", "-5"])
def test_invalid_max_tokens_fails_loudly(monkeypatch, raw):
    """Bad configuration must fail at startup, not mid-request."""
    monkeypatch.setenv("PNA_MAX_TOKENS", raw)
    with pytest.raises(ValueError, match="PNA_MAX_TOKENS"):
        load_settings()


def test_blank_max_tokens_falls_back_to_the_default(monkeypatch):
    """An empty variable is 'unset', not 'invalid'."""
    monkeypatch.setenv("PNA_MAX_TOKENS", "   ")
    assert load_settings().max_tokens == DEFAULT_MAX_TOKENS
