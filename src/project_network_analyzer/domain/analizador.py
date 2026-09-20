"""
analizador.py — Análisis estructural de la red de proyecto (Grupo 6).

Toma una `Red` ya construida y validada (ver `modelo.py`) y calcula sus
propiedades ESTRUCTURALES. No interviene tiempo, costo ni recursos: solo
la topología del DAG G = (V, E).

Análisis implementados:

  1. Ordenamiento topológico (orden de ejecución factible).
  2. Enumeración de los caminos fuente → sumidero.
  3. Centralidad de paso  σ(v)  y nodos críticos  V* = argmax σ(v).
  4. Cuellos de botella estructurales (nodos por los que pasan TODOS los
     caminos) y puntos de articulación del grafo no dirigido subyacente.
  5. Clasificación de actividades: iniciales, finales, intermedias y
     paralelas (generaciones topológicas / anticadenas).

Fórmula central — σ(v):

    σ(v) = (# caminos fuente → v) · (# caminos v → sumidero)

Se calcula con programación dinámica sobre el orden topológico en
O(|V| + |E|), evitando la explosión combinatoria de enumerar caminos:

    caminos_hasta(v) = 1                       si v es fuente
                     = Σ caminos_hasta(u)      para toda arista u → v

    caminos_desde(v) = 1                       si v es sumidero
                     = Σ caminos_desde(w)      para toda arista v → w

El número total de caminos fuente→sumidero es Σ caminos_hasta(t) sobre
todos los sumideros t (equivale a Σ caminos_desde(s) sobre las fuentes s).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from project_network_analyzer.domain.modelo import ErrorEstructuraRed, Red


@dataclass
class ResultadoAnalisis:
    """
    Resultado estructurado del análisis (determinista y serializable).

    Lo consume el reporte y el agente de IA. La IA NUNCA recalcula esto:
    solo lo interpreta.
    """

    orden_topologico: list[str]
    caminos: list[list[str]]
    numero_de_caminos: int
    centralidad: dict[str, int]            # σ(v) por actividad
    nodos_criticos: list[str]              # V* = argmax σ(v)
    sigma_maximo: int
    cuellos_de_botella: list[str]          # σ(v) == numero_de_caminos
    puntos_articulacion: list[str]         # grafo no dirigido subyacente
    iniciales: list[str]
    finales: list[str]
    intermedias: list[str]
    generaciones: list[list[str]]          # anticadenas: actividades paralelas
    caminos_truncados: bool = False        # True si se aplicó límite

    def resumen(self) -> str:
        """Resumen legible del análisis (para el reporte determinista)."""
        lineas = [
            f"Orden topológico   : {' → '.join(self.orden_topologico)}",
            f"Caminos f→s        : {self.numero_de_caminos}"
            + (" (lista truncada)" if self.caminos_truncados else ""),
            f"σ máximo           : {self.sigma_maximo}",
            f"Nodos críticos V*  : {', '.join(self.nodos_criticos)}",
            f"Cuellos de botella : {', '.join(self.cuellos_de_botella) or '(ninguno)'}",
            f"Ptos. articulación : {', '.join(self.puntos_articulacion) or '(ninguno)'}",
            f"Iniciales          : {', '.join(self.iniciales)}",
            f"Finales            : {', '.join(self.finales)}",
            f"Intermedias        : {', '.join(self.intermedias)}",
            f"Generaciones (||)  : {len(self.generaciones)} fases",
        ]
        return "\n".join(lineas)


class Analizador:
    """
    Calcula las propiedades estructurales de una `Red`.

    Se asume que la red ya fue validada (acíclica, débilmente conexa, con
    fuente y sumidero). Si no es acíclica, el análisis no tiene sentido y
    se aborta con `ErrorEstructuraRed`.
    """

    # Límite de seguridad para la ENUMERACIÓN de caminos (el conteo σ no
    # tiene límite porque es O(|V|+|E|)). Evita explosión combinatoria.
    LIMITE_CAMINOS = 10_000

    def __init__(self, red: Red) -> None:
        if not red.es_aciclico():
            raise ErrorEstructuraRed(
                "El análisis estructural requiere un DAG: la red contiene "
                f"un ciclo {red.detectar_ciclo()}."
            )
        self.red = red
        self.grafo: nx.DiGraph = red.grafo

    # ------------------------------------------------------------------ #
    # 1. Ordenamiento topológico
    # ------------------------------------------------------------------ #

    def orden_topologico(self) -> list[str]:
        """
        Un orden lineal de V tal que toda arista u→v cumple que u aparece
        antes que v: un orden de ejecución factible de las actividades.

        Se usa el orden topológico lexicográfico para que el resultado sea
        determinista (varios órdenes válidos son posibles).
        """
        return list(nx.lexicographical_topological_sort(self.grafo))

    # ------------------------------------------------------------------ #
    # 2. Caminos fuente → sumidero
    # ------------------------------------------------------------------ #

    def caminos_fuente_sumidero(
        self, limite: int | None = LIMITE_CAMINOS
    ) -> tuple[list[list[str]], bool]:
        """
        Enumera todos los caminos simples desde cualquier nodo fuente hasta
        cualquier nodo sumidero. En un DAG todo camino es simple.

        Devuelve (lista_de_caminos, truncado). Si se alcanza `limite`, la
        enumeración se detiene y `truncado=True` (el CONTEO exacto sigue
        disponible vía `numero_de_caminos()`).
        """
        caminos: list[list[str]] = []
        truncado = False
        for fuente in self.red.fuentes:
            for sumidero in self.red.sumideros:
                for camino in nx.all_simple_paths(self.grafo, fuente, sumidero):
                    caminos.append(camino)
                    if limite is not None and len(caminos) >= limite:
                        truncado = True
                        break
                if truncado:
                    break
            if truncado:
                break
        # Orden determinista.
        caminos.sort()
        return caminos, truncado

    # ------------------------------------------------------------------ #
    # 3. Centralidad de paso σ(v) y nodos críticos
    # ------------------------------------------------------------------ #

    def _caminos_hasta(self) -> dict[str, int]:
        """
        Programación dinámica sobre el orden topológico:

            caminos_hasta(v) = 1                  si v es fuente
                             = Σ caminos_hasta(u)  ∀ arista u→v

        Cuenta cuántos caminos distintos llegan a v desde alguna fuente.
        """
        hasta: dict[str, int] = {}
        for v in nx.topological_sort(self.grafo):
            predecesores = list(self.grafo.predecessors(v))
            if not predecesores:                       # v es fuente
                hasta[v] = 1
            else:
                hasta[v] = sum(hasta[u] for u in predecesores)
        return hasta

    def _caminos_desde(self) -> dict[str, int]:
        """
        Programación dinámica sobre el orden topológico inverso:

            caminos_desde(v) = 1                   si v es sumidero
                             = Σ caminos_desde(w)  ∀ arista v→w

        Cuenta cuántos caminos distintos salen de v hacia algún sumidero.
        """
        desde: dict[str, int] = {}
        for v in reversed(list(nx.topological_sort(self.grafo))):
            sucesores = list(self.grafo.successors(v))
            if not sucesores:                          # v es sumidero
                desde[v] = 1
            else:
                desde[v] = sum(desde[w] for w in sucesores)
        return desde

    def centralidad_de_paso(self) -> dict[str, int]:
        """
        σ(v) = caminos_hasta(v) · caminos_desde(v)

        Número de caminos fuente→sumidero que pasan por v. Se devuelve
        ordenado por id para que el resultado sea determinista.
        """
        hasta = self._caminos_hasta()
        desde = self._caminos_desde()
        return {v: hasta[v] * desde[v] for v in sorted(self.grafo.nodes)}

    def numero_de_caminos(self) -> int:
        """
        Número total de caminos fuente→sumidero.

        = Σ caminos_hasta(t) sobre todos los sumideros t. Es exacto y
        O(|V|+|E|): no depende de enumerar los caminos.
        """
        hasta = self._caminos_hasta()
        return sum(hasta[t] for t in self.red.sumideros)

    def nodos_criticos(self) -> tuple[list[str], int]:
        """
        V* = argmax_{v ∈ V} σ(v).

        Los nodos estructuralmente más críticos: aquellos por los que pasa
        el mayor número de caminos fuente→sumidero. Devuelve (V*, σ_máximo).
        """
        sigma = self.centralidad_de_paso()
        if not sigma:
            return [], 0
        maximo = max(sigma.values())
        criticos = sorted(v for v, s in sigma.items() if s == maximo)
        return criticos, maximo

    # ------------------------------------------------------------------ #
    # 4. Cuellos de botella y puntos de articulación
    # ------------------------------------------------------------------ #

    def cuellos_de_botella(self) -> list[str]:
        """
        Nodos por los que pasan TODOS los caminos fuente→sumidero, es decir
        σ(v) == número total de caminos.

        Son cuellos de botella estructurales: un fallo o bloqueo en ellos
        afecta a todas las secuencias posibles del proyecto. Incluye, por
        construcción, a la fuente y al sumidero únicos si los hubiera.
        """
        total = self.numero_de_caminos()
        sigma = self.centralidad_de_paso()
        return sorted(v for v, s in sigma.items() if s == total)

    def puntos_articulacion(self) -> list[str]:
        """
        Puntos de articulación del grafo NO dirigido subyacente: nodos
        cuya eliminación desconecta la red (aumenta el número de
        componentes conexas).

        Es un cuello de botella estructural más fuerte que `cuellos_de_botella`:
        no solo está en todos los caminos, sino que es el único enlace entre
        dos partes del proyecto. Los nodos de grado 1 (fuente/sumidero
        únicos) NO son puntos de articulación aunque sean obligatorios.
        """
        return sorted(nx.articulation_points(self.grafo.to_undirected()))

    # ------------------------------------------------------------------ #
    # 5. Clasificación de actividades
    # ------------------------------------------------------------------ #

    def clasificar_actividades(self) -> dict[str, list[str]]:
        """
        Clasifica V en:
          - iniciales  : nodos fuente   (δ⁻(v) = 0).
          - finales    : nodos sumidero (δ⁺(v) = 0).
          - intermedias: el resto (δ⁻(v) > 0 y δ⁺(v) > 0).
        """
        iniciales = set(self.red.fuentes)
        finales = set(self.red.sumideros)
        intermedias = sorted(
            v for v in self.grafo.nodes if v not in iniciales and v not in finales
        )
        return {
            "iniciales": self.red.fuentes,
            "finales": self.red.sumideros,
            "intermedias": intermedias,
        }

    def generaciones(self) -> list[list[str]]:
        """
        Generaciones topológicas (anticadenas): cada generación es un
        conjunto de actividades sin precedencia entre sí cuyos precedentes
        ya están en generaciones anteriores. Son las actividades que pueden
        ejecutarse EN PARALELO en esa fase del proyecto.
        """
        return [sorted(gen) for gen in nx.topological_generations(self.grafo)]

    def pares_paralelos(self) -> list[tuple[str, str]]:
        """
        Pares de actividades incomparables en el orden parcial del DAG: no
        existe camino dirigido entre ellas en ningún sentido, por lo que
        pueden ejecutarse en paralelo (noción más amplia que `generaciones`,
        que exige además compartir fase).
        """
        cierre = nx.transitive_closure_dag(self.grafo)
        nodos = sorted(self.grafo.nodes)
        pares: list[tuple[str, str]] = []
        for i, u in enumerate(nodos):
            for v in nodos[i + 1 :]:
                if not cierre.has_edge(u, v) and not cierre.has_edge(v, u):
                    pares.append((u, v))
        return pares

    # ------------------------------------------------------------------ #
    # Análisis agregado
    # ------------------------------------------------------------------ #

    def analizar(self, limite_caminos: int | None = LIMITE_CAMINOS) -> ResultadoAnalisis:
        """
        Ejecuta todo el análisis y devuelve un `ResultadoAnalisis`
        (determinista, sin efectos secundarios). Es la entrada que consume
        el agente de IA para interpretar — nunca para recalcular.
        """
        caminos, truncado = self.caminos_fuente_sumidero(limite_caminos)
        sigma = self.centralidad_de_paso()
        criticos, sigma_max = self.nodos_criticos()
        clases = self.clasificar_actividades()
        return ResultadoAnalisis(
            orden_topologico=self.orden_topologico(),
            caminos=caminos,
            numero_de_caminos=self.numero_de_caminos(),
            centralidad=sigma,
            nodos_criticos=criticos,
            sigma_maximo=sigma_max,
            cuellos_de_botella=self.cuellos_de_botella(),
            puntos_articulacion=self.puntos_articulacion(),
            iniciales=clases["iniciales"],
            finales=clases["finales"],
            intermedias=clases["intermedias"],
            generaciones=self.generaciones(),
            caminos_truncados=truncado,
        )
