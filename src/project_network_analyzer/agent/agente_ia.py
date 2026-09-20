"""
agente_ia.py — Capa LLM del agente híbrido (Grupo 6).

El agente del proyecto tiene dos capas. Esta es la SEGUNDA:

1. CAPA DETERMINISTA (reglas + plantillas) → `services/reporte.py`.
   Genera el reporte estructurado a partir del modelo y el analizador.

2. CAPA LLM (API de Claude) → este módulo.
   Recibe ese reporte ya construido como CONTEXTO y redacta una
   explicación en lenguaje natural o responde preguntas abiertas.

MODO FALLBACK: si no hay clave API (o falla la conexión), esta capa
devuelve un aviso y el sistema sigue entregando el reporte determinista
completo. Nunca queda inoperante.

IMPORTANTE (condición del proyecto): el LLM NUNCA hace el análisis
matemático. Nótese que este módulo no importa nada de `domain/`: solo
recibe y devuelve texto. La imposibilidad de calcular aquí es
estructural, no una convención.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from project_network_analyzer.agent import prompts

# Modelo de Claude por defecto. Es CONFIGURABLE: puede cambiarse al
# construir el agente (parámetro `modelo`) o editando esta constante.
# Alias válidos, p. ej.: "claude-haiku-4-5", "claude-sonnet-5".
# Haiku 4.5 es rápido y económico, suficiente para interpretar
# (no calcular) el análisis estructural.
MODELO_PREDETERMINADO = "claude-haiku-4-5"

# Valores de marcador del .env.example que NO son claves reales.
_CLAVES_DE_EJEMPLO = {"", "tu_clave_api_aqui", "tu_clave_aqui", "sk-ant-..."}


class AgenteIA:
    """
    Capa LLM del agente híbrido. Se activa solo si hay una clave API
    válida y la conexión responde; en cualquier otro caso cae al aviso de
    fallback, mientras la capa determinista sigue funcionando aparte.
    """

    def __init__(
        self, modelo: str | None = None, max_tokens: int = 4000
    ) -> None:
        load_dotenv()  # carga .env -> os.environ (clave nunca hardcodeada)

        self.modelo: str = modelo or MODELO_PREDETERMINADO
        self.max_tokens: int = max_tokens

        clave = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        self._clave_valida: bool = clave not in _CLAVES_DE_EJEMPLO
        self._cliente = None  # se crea de forma perezosa en _obtener_cliente

    # ------------------------------------------------------------------ #
    # Estado del agente
    # ------------------------------------------------------------------ #

    @property
    def llm_disponible(self) -> bool:
        """True si hay una clave API que parece válida (no de ejemplo)."""
        return self._clave_valida

    @property
    def modo(self) -> str:
        """Modo de operación actual, para mostrar en el reporte."""
        if self.llm_disponible:
            return f"híbrido (reglas + LLM: {self.modelo})"
        return "fallback (solo capa determinista de reglas)"

    def _obtener_cliente(self):
        """
        Crea (una sola vez) el cliente de Anthropic. Se importa aquí para
        que el proyecto siga funcionando aunque `anthropic` no esté
        instalado: en ese caso se cae a modo fallback.
        """
        if self._cliente is not None:
            return self._cliente
        import anthropic  # import local: si falla, fallback

        # La clave se toma de ANTHROPIC_API_KEY (cargada de .env). No se
        # imprime ni se registra en ningún momento.
        self._cliente = anthropic.Anthropic()
        return self._cliente

    # ------------------------------------------------------------------ #
    # Interpretación en lenguaje natural
    # ------------------------------------------------------------------ #

    def _llamar_llm(self, reporte_estructurado: str, instruccion: str) -> str:
        """
        Llama a la API de Claude. El reporte va como bloque de sistema con
        cache_control (es el contexto estable reutilizado entre llamadas);
        la instrucción/pregunta variable va en el mensaje de usuario.

        Cualquier fallo (sin SDK, sin clave, red caída, error de API) se
        captura y se cae al modo fallback: nunca lanza hacia el usuario.
        """
        try:
            import anthropic

            cliente = self._obtener_cliente()
            respuesta = cliente.messages.create(
                model=self.modelo,
                max_tokens=self.max_tokens,
                system=[
                    {"type": "text", "text": prompts.SISTEMA},
                    {
                        "type": "text",
                        "text": prompts.contexto_del_reporte(
                            reporte_estructurado
                        ),
                        # Contexto estable y reutilizado -> se cachea.
                        "cache_control": {"type": "ephemeral"},
                    },
                ],
                messages=[{"role": "user", "content": instruccion}],
            )
            partes = [b.text for b in respuesta.content if b.type == "text"]
            return "\n".join(partes).strip() or self._aviso_fallback(
                "El modelo no devolvió texto."
            )
        except anthropic.AuthenticationError:
            return self._aviso_fallback("clave API inválida o sin permisos")
        except anthropic.APIConnectionError:
            return self._aviso_fallback("sin conexión con la API")
        except anthropic.APIStatusError as e:
            return self._aviso_fallback(f"error de API ({e.status_code})")
        except ModuleNotFoundError:
            return self._aviso_fallback("el paquete 'anthropic' no está instalado")
        except Exception as e:  # red de seguridad: jamás romper el flujo
            return self._aviso_fallback(f"error inesperado: {type(e).__name__}")

    @staticmethod
    def _aviso_fallback(motivo: str) -> str:
        """Mensaje que sustituye a la respuesta LLM en modo fallback."""
        return (
            "[MODO FALLBACK — capa LLM no disponible: "
            f"{motivo}]\n"
            "El reporte estructurado de la sección anterior contiene el "
            "análisis completo y es válido por sí mismo. La interpretación "
            "en lenguaje natural requiere la capa LLM."
        )

    def interpretar(self, reporte_estructurado: str) -> str:
        """
        Redacta una interpretación en lenguaje natural del reporte
        estructurado (resumen ejecutivo + lectura de los hallazgos +
        sugerencias estructurales). En fallback devuelve el aviso.
        """
        if not self.llm_disponible:
            return self._aviso_fallback("no hay clave API configurada")
        return self._llamar_llm(
            reporte_estructurado, prompts.INSTRUCCION_INTERPRETAR
        )

    def responder(self, pregunta: str, reporte_estructurado: str) -> str:
        """
        Responde una pregunta abierta del usuario sobre la red, usando solo
        la información del reporte estructurado. En fallback avisa que la
        respuesta libre necesita la capa LLM.
        """
        if not self.llm_disponible:
            return self._aviso_fallback("no hay clave API configurada")
        return self._llamar_llm(
            reporte_estructurado, prompts.instruccion_responder(pregunta)
        )
