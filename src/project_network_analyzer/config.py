"""
config.py — Runtime configuration.

Everything the application needs from the environment — the LLM layer's
settings and the database location — is read here, once, and handed over
as a `Settings` object. The model id in particular is configuration, not
a constant buried in the agent.

`domain/` reads nothing from the environment: its one tunable, `StructuralAnalyzer.PATH_LIMIT`, is an
algorithmic safeguard rather than a deployment knob, and keeping it a
plain constant is what keeps the domain pure.

Environment variables:

    ANTHROPIC_API_KEY   the API key. Absent or left as the placeholder
                        from .env.example -> the agent runs in fallback.
    PNA_MODEL           Claude model id. Default: DEFAULT_MODEL.
    PNA_MAX_TOKENS      response cap. Default: DEFAULT_MAX_TOKENS.
    PNA_DATABASE_URL    PostgreSQL URL. Absent -> the API runs without
                        persistence and the /networks endpoints answer 503.

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

# Placeholder values from .env.example that are NOT real keys. The
# Spanish ones come from earlier versions of that file and stay listed so
# an existing .env copied from it still falls back cleanly.
PLACEHOLDER_KEYS = frozenset(
    {"", "your_api_key_here", "sk-ant-...", "tu_clave_api_aqui", "tu_clave_aqui"}
)


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for one application instance."""

    api_key: str
    model: str
    max_tokens: int
    database_url: str | None = None

    @property
    def api_key_is_usable(self) -> bool:
        """True when a key is present and is not a placeholder."""
        return self.api_key not in PLACEHOLDER_KEYS


def load_settings(
    model: str | None = None,
    max_tokens: int | None = None,
    database_url: str | None = None,
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
                    f"PNA_MAX_TOKENS must be a positive integer, not {raw!r}."
                ) from None
    if max_tokens <= 0:
        raise ValueError(
            f"PNA_MAX_TOKENS must be a positive integer, not {max_tokens!r}."
        )

    resolved_database_url = (
        database_url or os.environ.get("PNA_DATABASE_URL", "").strip() or None
    )

    return Settings(
        api_key=api_key,
        model=resolved_model,
        max_tokens=max_tokens,
        database_url=resolved_database_url,
    )
