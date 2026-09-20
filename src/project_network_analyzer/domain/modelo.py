"""
modelo.py — Modelo matemático de la red de proyecto (Grupo 6).

Representa un proyecto como un grafo dirigido acíclico (DAG)

        G = (V, E)

donde:
    - V = conjunto de actividades del proyecto.
    - E ⊆ V × V = relaciones de precedencia. Existe la arista (P, A) si la
      actividad P es precedente de A, es decir, P debe terminar antes de
      que A pueda iniciar.

La clase `Red` carga el caso desde un JSON, construye el grafo con
`networkx` y valida las cuatro restricciones estructurales del modelo:

    1. Aciclicidad        : no existe ningún ciclo dirigido en G.
    2. Conectividad débil : el grafo no dirigido subyacente es conexo.
    3. Nodo(s) fuente     : ∃ v ∈ V con grado de entrada δ⁻(v) = 0.
    4. Nodo(s) sumidero   : ∃ v ∈ V con grado de salida  δ⁺(v) = 0.

Este módulo NO realiza el análisis estructural (caminos, centralidad,
articulación): de eso se encarga `analizador.py`. Aquí solo se construye y
se valida la estructura.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx


class ErrorEstructuraRed(Exception):
    """La red no cumple alguna restricción estructural del modelo."""


@dataclass
class ResultadoValidacion:
    """
    Resultado estructurado de validar las restricciones del modelo.

    Es un objeto de datos puro (determinista y serializable) para que tanto
    los tests como el agente de IA puedan consumirlo sin ambigüedad.
    """

    es_aciclico: bool
    es_debilmente_conexo: bool
    fuentes: list[str]
    sumideros: list[str]
    # Si NO es acíclico, aquí van los nodos del ciclo detectado (evidencia).
    ciclo_detectado: list[str] = field(default_factory=list)

    @property
    def es_valida(self) -> bool:
        """
        La red es estructuralmente válida si cumple las 4 restricciones:
        acíclica, débilmente conexa y con al menos un nodo fuente y un
        nodo sumidero.
        """
        return (
            self.es_aciclico
            and self.es_debilmente_conexo
            and len(self.fuentes) >= 1
            and len(self.sumideros) >= 1
        )

    def resumen(self) -> str:
        """Resumen legible del resultado (para reporte y depuración)."""
        estado = "VÁLIDA" if self.es_valida else "INVÁLIDA"
        lineas = [
            f"Validación estructural: {estado}",
            f"  - Acíclica          : {'sí' if self.es_aciclico else 'NO'}",
            f"  - Débilmente conexa : {'sí' if self.es_debilmente_conexo else 'NO'}",
            f"  - Fuentes  δ⁻(v)=0  : {', '.join(self.fuentes) or '(ninguna)'}",
            f"  - Sumideros δ⁺(v)=0 : {', '.join(self.sumideros) or '(ninguno)'}",
        ]
        if not self.es_aciclico and self.ciclo_detectado:
            lineas.append(
                f"  - Ciclo detectado   : {' → '.join(self.ciclo_detectado)}"
            )
        return "\n".join(lineas)


class Red:
    """
    Red de proyecto modelada como DAG G = (V, E).

    Cada actividad es un nodo con los atributos `nombre` y `descripcion`.
    Cada relación de precedencia (P precede a A) es una arista dirigida P → A.
    """

    def __init__(self, nombre_proyecto: str, descripcion: str = "") -> None:
        self.nombre_proyecto: str = nombre_proyecto
        self.descripcion: str = descripcion
        # Grafo dirigido subyacente. Es la representación canónica de G.
        self.grafo: nx.DiGraph = nx.DiGraph()

    # ------------------------------------------------------------------ #
    # Construcción
    # ------------------------------------------------------------------ #

    def agregar_actividad(
        self, id_actividad: str, nombre: str, descripcion: str = ""
    ) -> None:
        """
        Añade un nodo (actividad) a V.

        Lanza ErrorEstructuraRed si el id ya existe (ids duplicados harían
        ambigua la red).
        """
        if id_actividad in self.grafo:
            raise ErrorEstructuraRed(
                f"Actividad duplicada: '{id_actividad}' ya existe en la red."
            )
        self.grafo.add_node(id_actividad, nombre=nombre, descripcion=descripcion)

    def agregar_precedencia(self, precedente: str, actividad: str) -> None:
        """
        Añade la arista `precedente → actividad` a E.

        Modela la relación: `precedente` debe terminar antes de iniciar
        `actividad`. Ambos nodos deben existir previamente en V.
        """
        for nodo in (precedente, actividad):
            if nodo not in self.grafo:
                raise ErrorEstructuraRed(
                    f"Precedencia inválida: la actividad '{nodo}' no existe. "
                    f"(Relación '{precedente}' → '{actividad}')."
                )
        if precedente == actividad:
            # Un bucle v→v es un ciclo trivial: viola la aciclicidad.
            raise ErrorEstructuraRed(
                f"Una actividad no puede precederse a sí misma: '{precedente}'."
            )
        self.grafo.add_edge(precedente, actividad)

    @classmethod
    def desde_json(cls, ruta: str | Path) -> "Red":
        """
        Construye una Red a partir de un archivo JSON con el formato:

            {
              "proyecto": {"nombre": ..., "descripcion": ...},
              "actividades": [
                {"id": "A", "nombre": ..., "descripcion": ...,
                 "precedentes": ["..."]},
                ...
              ]
            }

        Las actividades se cargan primero (V) y luego las precedencias (E),
        de modo que el orden de aparición en el JSON no importa.
        """
        ruta = Path(ruta)
        if not ruta.is_file():
            raise ErrorEstructuraRed(f"No se encontró el archivo: {ruta}")

        with ruta.open(encoding="utf-8") as f:
            datos = json.load(f)

        meta = datos.get("proyecto", {})
        red = cls(
            nombre_proyecto=meta.get("nombre", ruta.stem),
            descripcion=meta.get("descripcion", ""),
        )

        actividades = datos.get("actividades", [])
        if not actividades:
            raise ErrorEstructuraRed(
                "El JSON no contiene actividades ('actividades' vacío o ausente)."
            )

        # Paso 1: cargar todos los nodos (V).
        for act in actividades:
            red.agregar_actividad(
                id_actividad=act["id"],
                nombre=act.get("nombre", act["id"]),
                descripcion=act.get("descripcion", ""),
            )

        # Paso 2: cargar las precedencias (E) una vez que V está completo.
        for act in actividades:
            for precedente in act.get("precedentes", []):
                red.agregar_precedencia(precedente, act["id"])

        return red

    # ------------------------------------------------------------------ #
    # Accesores estructurales
    # ------------------------------------------------------------------ #

    @property
    def actividades(self) -> list[str]:
        """V: lista de ids de actividad, ordenada para ser determinista."""
        return sorted(self.grafo.nodes)

    @property
    def precedencias(self) -> list[tuple[str, str]]:
        """E: lista de aristas (precedente, actividad), ordenada."""
        return sorted(self.grafo.edges)

    @property
    def fuentes(self) -> list[str]:
        """
        Nodos fuente: actividades con grado de entrada δ⁻(v) = 0
        (no tienen precedentes → son actividades iniciales del proyecto).
        """
        return sorted(v for v in self.grafo.nodes if self.grafo.in_degree(v) == 0)

    @property
    def sumideros(self) -> list[str]:
        """
        Nodos sumidero: actividades con grado de salida δ⁺(v) = 0
        (no preceden a ninguna otra → son actividades finales del proyecto).
        """
        return sorted(v for v in self.grafo.nodes if self.grafo.out_degree(v) == 0)

    def nombre_de(self, id_actividad: str) -> str:
        """Nombre legible de una actividad a partir de su id."""
        if id_actividad not in self.grafo:
            raise ErrorEstructuraRed(f"Actividad inexistente: '{id_actividad}'.")
        return self.grafo.nodes[id_actividad].get("nombre", id_actividad)

    # ------------------------------------------------------------------ #
    # Validaciones estructurales (restricciones del modelo)
    # ------------------------------------------------------------------ #

    def es_aciclico(self) -> bool:
        """
        Restricción 1 — Aciclicidad.

        True si G no contiene ningún ciclo dirigido. Se delega en el
        algoritmo de networkx (basado en orden topológico / DFS).
        """
        return nx.is_directed_acyclic_graph(self.grafo)

    def detectar_ciclo(self) -> list[str]:
        """
        Devuelve la secuencia de nodos de un ciclo dirigido si existe;
        lista vacía si el grafo es acíclico. Sirve como evidencia para
        explicar por qué la red es inválida.
        """
        try:
            aristas_ciclo = nx.find_cycle(self.grafo, orientation="original")
        except nx.NetworkXNoCycle:
            return []
        # find_cycle devuelve aristas (u, v, dir); reconstruimos la secuencia.
        nodos = [u for u, _v, *_ in aristas_ciclo]
        nodos.append(aristas_ciclo[-1][1])  # cerrar el ciclo con el último v
        return nodos

    def es_debilmente_conexo(self) -> bool:
        """
        Restricción 2 — Conectividad débil.

        True si el grafo NO dirigido subyacente es conexo, es decir, todas
        las actividades pertenecen a la misma componente (no hay sub-redes
        desconectadas). Un grafo vacío no se considera conexo.
        """
        if self.grafo.number_of_nodes() == 0:
            return False
        return nx.is_weakly_connected(self.grafo)

    def validar(self) -> ResultadoValidacion:
        """
        Evalúa las 4 restricciones del modelo y devuelve un
        `ResultadoValidacion` (determinista, sin efectos secundarios).
        """
        aciclico = self.es_aciclico()
        return ResultadoValidacion(
            es_aciclico=aciclico,
            es_debilmente_conexo=self.es_debilmente_conexo(),
            fuentes=self.fuentes,
            sumideros=self.sumideros,
            ciclo_detectado=[] if aciclico else self.detectar_ciclo(),
        )

    def exigir_valida(self) -> ResultadoValidacion:
        """
        Igual que `validar()`, pero lanza `ErrorEstructuraRed` si la red
        no cumple alguna restricción. Útil para abortar temprano en el
        orquestador antes del análisis.
        """
        resultado = self.validar()
        if not resultado.es_valida:
            raise ErrorEstructuraRed(
                "La red no es estructuralmente válida:\n" + resultado.resumen()
            )
        return resultado

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #

    def __len__(self) -> int:
        """Número de actividades |V|."""
        return self.grafo.number_of_nodes()

    def __repr__(self) -> str:
        return (
            f"Red(proyecto={self.nombre_proyecto!r}, "
            f"|V|={self.grafo.number_of_nodes()}, "
            f"|E|={self.grafo.number_of_edges()})"
        )
