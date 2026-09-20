"""
config.py — Runtime configuration for the LLM layer.

Everything the agent needs from the environment is read here, once, and
handed over as a `Settings` object. The model id in particular is
configuration, not a constant buried in the agent.

Only the LLM layer is configured here. `domain/` reads nothing from the
environment: its one tunable, `StructuralAnalyzer.PATH_LIMIT`, is an
algorithmic safeguard rather than a deployment knob, and keeping it a
plain constant is what keeps the domain pure.

Environment variables:

    ANTHROPIC_API_KEY   the API key. Absent or left as the placeholder
                        from .env.example -> the agent runs in fallback.
    PNA_MODEL           Claude model id. Default: DEFAULT_MODEL.
    PNA_MAX_TOKENS      response cap. Default: DEFAULT_MAX_TOKENS.

Settings are read on each `load_settings()` call rather than at import
time, so tests can set the environment before building an agent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Claude model used to interpret (never to compute) the analysis. Haiku
# 4.5 is fast and cheap, which is plenty for the job; "claude-sonnet-5"
# is the option when output quality matters more than cost.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 4000

# Placeholder values from .env.example that are NOT real keys.
PLACEHOLDER_KEYS = frozenset(
    {"", "tu_clave_api_aqui", "tu_clave_aqui", "sk-ant-..."}
)


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for one agent instance."""

    api_key: str
    model: str
    max_tokens: int

    @property
    def api_key_is_usable(self) -> bool:
        """True when a key is present and is not a placeholder."""
        return self.api_key not in PLACEHOLDER_KEYS


def load_settings(
    model: str | None = None, max_tokens: int | None = None
) -> Settings:
    """
    Resolve the configuration, in order of precedence: explicit argument,
    then environment variable, then default.

    `.env` is loaded into the environment first, and never overrides
    variables that are already set.

    Raises ValueError when PNA_MAX_TOKENS is set to something that is not
    a positive integer: bad configuration should fail loudly at startup,
    not silently halfway through a request.
    """
    load_dotenv()  # .env -> os.environ (the key is never hardcoded)

    api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
    resolved_model = model or os.environ.get("PNA_MODEL") or DEFAULT_MODEL

    if max_tokens is None:
        raw = os.environ.get("PNA_MAX_TOKENS")
        if raw is None or raw.strip() == "":
            max_tokens = DEFAULT_MAX_TOKENS
        else:
            try:
                max_tokens = int(raw)
            except ValueError:
                raise ValueError(
                    f"PNA_MAX_TOKENS debe ser un entero positivo, no {raw!r}."
                ) from None
    if max_tokens <= 0:
        raise ValueError(
            f"PNA_MAX_TOKENS debe ser un entero positivo, no {max_tokens!r}."
        )

    return Settings(api_key=api_key, model=resolved_model, max_tokens=max_tokens)
