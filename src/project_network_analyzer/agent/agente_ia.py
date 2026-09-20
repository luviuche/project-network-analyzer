"""
agente_ia.py — Agente de IA híbrido (reglas + LLM) (Grupo 6).

El agente tiene dos capas:

1. CAPA DETERMINISTA (reglas + plantillas):
   Toma `ResultadoValidacion` y `ResultadoAnalisis` y genera un reporte
   estructurado en texto, detectando patrones con reglas fijas
   (caminos críticos, puntos de articulación, actividades paralelas...).
   Es 100 % determinista y testeable.

2. CAPA LLM (API de Claude):
   Recibe el reporte estructurado como CONTEXTO y redacta una explicación
   en lenguaje natural, responde preguntas abiertas y sugiere mejoras
   estructurales.

MODO FALLBACK: si no hay clave API (o falla la conexión), el agente usa
solo la capa determinista. Nunca queda inoperante.

IMPORTANTE (condición del proyecto): el LLM NUNCA hace el análisis
matemático; solo INTERPRETA los resultados que produce el modelo. Toda
la matemática vive en `modelo.py` y `analizador.py`.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from project_network_analyzer.domain.analizador import ResultadoAnalisis
from project_network_analyzer.domain.modelo import Red, ResultadoValidacion

# Modelo de Claude por defecto. Es CONFIGURABLE: puede cambiarse al
# construir el agente (parámetro `modelo`) o editando esta constante.
# Alias válidos, p. ej.: "claude-haiku-4-5", "claude-sonnet-4-6",
# "claude-opus-4-7". Haiku 4.5 es rápido y económico, suficiente para
# interpretar (no calcular) el análisis estructural.
MODELO_PREDETERMINADO = "claude-haiku-4-5"

# Valores de marcador del .env.example que NO son claves reales.
_CLAVES_DE_EJEMPLO = {"", "tu_clave_api_aqui", "tu_clave_aqui", "sk-ant-..."}


class AgenteIA:
    """
    Agente híbrido. La capa determinista siempre funciona; la capa LLM
    se activa solo si hay una clave API válida y la conexión responde.
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
    # 1. CAPA DETERMINISTA — reporte estructurado por reglas
    # ------------------------------------------------------------------ #

    def generar_reporte_estructurado(
        self,
        red: Red,
        validacion: ResultadoValidacion,
        analisis: ResultadoAnalisis,
    ) -> str:
        """
        Construye el reporte estructurado en texto a partir de los
        resultados del modelo. Es la salida determinista del agente y
        también el CONTEXTO que se entrega a la capa LLM.
        """
        lineas: list[str] = []
        ad = lineas.append

        ad("=" * 64)
        ad(f"PROYECTO: {red.nombre_proyecto}")
        if red.descripcion:
            ad(red.descripcion)
        ad(f"Actividades |V| = {len(red)}   Precedencias |E| = "
           f"{red.grafo.number_of_edges()}")
        ad("=" * 64)

        ad("\n[1] VALIDACIÓN ESTRUCTURAL")
        ad(validacion.resumen())

        ad("\n[2] ANÁLISIS ESTRUCTURAL")
        ad(analisis.resumen())
        ad("\nCentralidad de paso σ(v) (caminos f→s que pasan por v):")
        for v, s in sorted(
            analisis.centralidad.items(), key=lambda kv: (-kv[1], kv[0])
        ):
            ad(f"  {v} ({red.nombre_de(v)}): σ = {s}")

        ad("\nClasificación de actividades:")
        ad(f"  Iniciales : {self._con_nombres(red, analisis.iniciales)}")
        ad(f"  Finales   : {self._con_nombres(red, analisis.finales)}")
        ad(f"  Intermedias: {self._con_nombres(red, analisis.intermedias)}")

        ad("\nFases (generaciones topológicas — actividades en paralelo):")
        for i, gen in enumerate(analisis.generaciones):
            marca = "  ← paralelas" if len(gen) > 1 else ""
            ad(f"  Fase {i}: {self._con_nombres(red, gen)}{marca}")

        ad("\n[3] HALLAZGOS DETECTADOS POR REGLAS")
        for hallazgo in self._detectar_patrones(red, validacion, analisis):
            ad(f"  - {hallazgo}")

        return "\n".join(lineas)

    @staticmethod
    def _con_nombres(red: Red, ids: list[str]) -> str:
        """Formatea 'A (nombre), B (nombre)' para legibilidad del reporte."""
        if not ids:
            return "(ninguna)"
        return ", ".join(f"{i} ({red.nombre_de(i)})" for i in ids)

    def _detectar_patrones(
        self,
        red: Red,
        validacion: ResultadoValidacion,
        analisis: ResultadoAnalisis,
    ) -> list[str]:
        """
        Reglas deterministas que traducen los números del análisis en
        afirmaciones estructurales. Estas frases son la materia prima que
        el LLM luego redacta en lenguaje natural.
        """
        h: list[str] = []

        if not validacion.es_valida:
            h.append(
                "La red NO es estructuralmente válida: no se cumple alguna "
                "restricción del modelo (ver sección [1])."
            )
            if validacion.ciclo_detectado:
                h.append(
                    "Se detectó un ciclo dirigido: "
                    f"{' → '.join(validacion.ciclo_detectado)}. Un proyecto "
                    "no puede tener dependencias circulares."
                )

        n = analisis.numero_de_caminos
        if n > 1:
            h.append(
                f"Existen {n} caminos estructurales distintos de la fuente al "
                "sumidero: el proyecto admite múltiples secuencias de ejecución."
            )
        elif n == 1:
            h.append(
                "Existe un único camino fuente→sumidero: la red es una cadena "
                "sin alternativas estructurales."
            )

        for v in analisis.puntos_articulacion:
            h.append(
                f"El nodo {v} ({red.nombre_de(v)}) es un PUNTO DE ARTICULACIÓN: "
                "su eliminación desconectaría la red. Es un cuello de botella "
                "estructural crítico; conviene mitigar su riesgo."
            )

        cuellos_no_art = [
            c for c in analisis.cuellos_de_botella
            if c not in analisis.puntos_articulacion
        ]
        if cuellos_no_art:
            h.append(
                "Pasan TODOS los caminos por: "
                f"{', '.join(cuellos_no_art)}. Son obligatorios en cualquier "
                "ejecución (aunque no desconectan la red)."
            )

        if analisis.nodos_criticos:
            h.append(
                f"Nodos críticos V* = {{{', '.join(analisis.nodos_criticos)}}} "
                f"con σ máximo = {analisis.sigma_maximo}: concentran el mayor "
                "paso de caminos y son los más sensibles estructuralmente."
            )

        # Paralelismo en la primera fase con más de una actividad.
        for i, gen in enumerate(analisis.generaciones):
            if len(gen) > 1:
                h.append(
                    f"En la fase {i} hay {len(gen)} actividades que pueden "
                    f"ejecutarse en paralelo: {', '.join(gen)}."
                )
                break

        total_paralelas = sum(
            1 for g in analisis.generaciones if len(g) > 1
        )
        if total_paralelas:
            h.append(
                f"Hay {total_paralelas} fase(s) con paralelismo estructural: "
                "permiten acortar la ruta del proyecto si hay recursos."
            )

        return h

    # ------------------------------------------------------------------ #
    # 2. CAPA LLM — interpretación en lenguaje natural
    # ------------------------------------------------------------------ #

    _SISTEMA = (
        "Eres un asistente experto en Investigación de Operaciones, "
        "especializado en el ANÁLISIS ESTRUCTURAL de redes de proyectos "
        "(grafos dirigidos acíclicos). Trabajas para un proyecto "
        "universitario del Grupo 6.\n\n"
        "Se te entrega un REPORTE ESTRUCTURADO ya calculado por un modelo "
        "matemático determinista. Tu tarea es ÚNICAMENTE interpretarlo: "
        "explicarlo en lenguaje natural claro, responder preguntas y "
        "sugerir mejoras estructurales.\n\n"
        "REGLAS ESTRICTAS:\n"
        "- NUNCA recalcules ni inventes números: usa solo los del reporte.\n"
        "- Si un dato no está en el reporte, dilo explícitamente.\n"
        "- No trates duración, costos ni recursos: el alcance es ESTRUCTURAL.\n"
        "- Responde en español, con precisión técnica pero accesible."
    )

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
                    {"type": "text", "text": self._SISTEMA},
                    {
                        "type": "text",
                        "text": (
                            "REPORTE ESTRUCTURADO (fuente única de verdad):\n\n"
                            + reporte_estructurado
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
        instruccion = (
            "Redacta una interpretación del reporte estructurado para el "
            "informe del proyecto, con esta estructura:\n"
            "1) Resumen ejecutivo (3-4 frases).\n"
            "2) Lectura de los nodos críticos y puntos de articulación: qué "
            "implican para la planeación del proyecto de software.\n"
            "3) Lectura del paralelismo entre actividades.\n"
            "4) Sugerencias para mejorar la ESTRUCTURA de la red "
            "(sin hablar de tiempos ni costos)."
        )
        return self._llamar_llm(reporte_estructurado, instruccion)

    def responder(self, pregunta: str, reporte_estructurado: str) -> str:
        """
        Responde una pregunta abierta del usuario sobre la red, usando solo
        la información del reporte estructurado. En fallback avisa que la
        respuesta libre necesita la capa LLM.
        """
        if not self.llm_disponible:
            return self._aviso_fallback("no hay clave API configurada")
        instruccion = (
            "Pregunta del usuario sobre la red de este proyecto:\n"
            f"«{pregunta}»\n\n"
            "Responde apoyándote EXCLUSIVAMENTE en el reporte estructurado. "
            "Si la respuesta no se puede deducir del reporte, dilo claramente."
        )
        return self._llamar_llm(reporte_estructurado, instruccion)
