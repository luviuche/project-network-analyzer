"""
llm_agent.py — The LLM layer of the hybrid agent.

The project's agent has two layers. This is the SECOND one:

1. THE RULE LAYER (deterministic) → `services/report.py`.
   Builds the structured report from the model and the analyser.

2. THE LLM LAYER (Claude API) → this module.
   Takes that finished report as CONTEXT and writes a natural-language
   explanation, or answers open questions about it.

FALLBACK MODE: with no API key (or on a failed connection) this layer
returns a notice and the system still delivers the complete
deterministic report. It is never left inoperable.

IMPORTANT (the project's one rule): the LLM never does the mathematics.
Note that this module imports nothing from `domain/`: it only takes text
in and gives text back. Being unable to compute here is structural, not
a convention.

The model id and the token cap come from `config.py`, not from
constants here.

Prompt and notice text is Spanish because it is user-facing output; the
identifiers, docstrings and comments around it are English.
"""

from __future__ import annotations

from project_network_analyzer.agent import prompts
from project_network_analyzer.config import Settings, load_settings


class LLMAgent:
    """
    The LLM layer of the hybrid agent. It engages only when there is a
    valid-looking API key and the connection answers; in every other case
    it falls back to a notice, while the rule layer keeps working on its
    own.
    """

    def __init__(
        self,
        model: str | None = None,
        max_tokens: int | None = None,
        settings: Settings | None = None,
    ) -> None:
        # `settings` lets a caller inject a resolved configuration (the
        # API layer will); otherwise it is read from the environment.
        self.settings: Settings = settings or load_settings(
            model=model, max_tokens=max_tokens
        )
        self._client = None  # created lazily in _get_client

    @property
    def model(self) -> str:
        """The Claude model id this agent calls."""
        return self.settings.model

    @property
    def max_tokens(self) -> int:
        """Cap on the response length."""
        return self.settings.max_tokens

    # ------------------------------------------------------------------ #
    # Agent state
    # ------------------------------------------------------------------ #

    @property
    def llm_available(self) -> bool:
        """True when an API key is present and is not a placeholder."""
        return self.settings.api_key_is_usable

    @property
    def mode(self) -> str:
        """Current operating mode, for display in the report."""
        if self.llm_available:
            return f"híbrido (reglas + LLM: {self.model})"
        return "fallback (solo capa determinista de reglas)"

    def _get_client(self):
        """
        Create the Anthropic client, once. Imported here so the project
        keeps working when `anthropic` is not installed: that case falls
        back instead.
        """
        if self._client is not None:
            return self._client
        import anthropic  # local import: falls back if it fails

        # The key comes from ANTHROPIC_API_KEY (loaded from .env). It is
        # never printed or logged.
        self._client = anthropic.Anthropic()
        return self._client

    # ------------------------------------------------------------------ #
    # Natural-language interpretation
    # ------------------------------------------------------------------ #

    def _call_llm(self, structured_report: str, instruction: str) -> str:
        """
        Call the Claude API. The report goes in a system block with
        cache_control (it is the stable context reused across calls); the
        variable instruction or question goes in the user message.

        Every failure (no SDK, no key, network down, API error) is caught
        and falls back: nothing is ever raised at the user.
        """
        # The import gets its own try, separate from the one wrapping the
        # call: the `except anthropic.X` handlers below have to evaluate
        # the name `anthropic`, so this import must have happened before
        # that block can handle anything.
        try:
            import anthropic
        except ModuleNotFoundError:
            return self._fallback_notice("el paquete 'anthropic' no está instalado")

        try:
            client = self._get_client()
            response = client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=[
                    {"type": "text", "text": prompts.SYSTEM},
                    {
                        "type": "text",
                        "text": prompts.report_context(structured_report),
                        # Stable, reused context -> worth caching.
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                messages=[{"role": "user", "content": instruction}],
            )
            parts = [b.text for b in response.content if b.type == "text"]
            return "\n".join(parts).strip() or self._fallback_notice(
                "El modelo no devolvió texto."
            )
        except anthropic.AuthenticationError:
            return self._fallback_notice("clave API inválida o sin permisos")
        except anthropic.APIConnectionError:
            return self._fallback_notice("sin conexión con la API")
        except anthropic.APIStatusError as e:
            return self._fallback_notice(f"error de API ({e.status_code})")
        except Exception as e:  # safety net: never break the flow
            return self._fallback_notice(f"error inesperado: {type(e).__name__}")

    @staticmethod
    def _fallback_notice(reason: str) -> str:
        """The message that replaces the LLM answer in fallback mode."""
        return (
            "[MODO FALLBACK — capa LLM no disponible: "
            f"{reason}]\n"
            "El reporte estructurado de la sección anterior contiene el "
            "análisis completo y es válido por sí mismo. La interpretación "
            "en lenguaje natural requiere la capa LLM."
        )

    def interpret(self, structured_report: str) -> str:
        """
        Write a natural-language interpretation of the structured report
        (executive summary + reading of the findings + structural
        suggestions). In fallback mode it returns the notice.
        """
        if not self.llm_available:
            return self._fallback_notice("no hay clave API configurada")
        return self._call_llm(structured_report, prompts.INTERPRET_INSTRUCTION)

    def answer(self, question: str, structured_report: str) -> str:
        """
        Answer an open question about the network using only what is in
        the structured report. In fallback mode it says that a free-form
        answer needs the LLM layer.
        """
        if not self.llm_available:
            return self._fallback_notice("no hay clave API configurada")
        return self._call_llm(
            structured_report, prompts.answer_instruction(question)
        )
