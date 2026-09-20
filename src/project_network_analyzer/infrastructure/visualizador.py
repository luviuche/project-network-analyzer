"""
visualizador.py — Visualización del grafo de la red de proyecto (Grupo 6).

Dibuja el DAG G = (V, E) con `networkx` + `matplotlib` y lo guarda en
`outputs/grafo_red.png`. El dibujo es ESTRUCTURAL: no representa tiempos ni
costos, solo la topología y los roles estructurales detectados por el
`Analizador`.

Disposición: layout multipartito por GENERACIONES topológicas (cada columna
es una fase; las actividades de una misma columna pueden ir en paralelo),
de izquierda a derecha desde la(s) fuente(s) hasta el/los sumidero(s).

Codificación visual:
  - Color de relleno = rol estructural (fuente / sumidero / crítico / normal).
  - Borde grueso morado = punto de articulación (cuello de botella fuerte).
  - Etiqueta = id de la actividad y su centralidad σ(v).

No usa backend interactivo (Agg): funciona sin entorno gráfico, como exige
ejecutar `python src/main.py` en cualquier máquina.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend headless: imprescindible antes de pyplot

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import networkx as nx

from project_network_analyzer.domain.analizador import ResultadoAnalisis
from project_network_analyzer.domain.modelo import Red

# Paleta (rol estructural -> color de relleno).
_COLOR_FUENTE = "#2e7d32"      # verde  : actividad inicial (δ⁻=0)
_COLOR_SUMIDERO = "#c62828"    # rojo   : actividad final   (δ⁺=0)
_COLOR_CRITICO = "#ef6c00"     # naranja: nodo crítico V* = argmax σ(v)
_COLOR_NORMAL = "#90caf9"      # azul   : actividad intermedia
_BORDE_ARTICULACION = "#6a1b9a"  # morado: punto de articulación


class Visualizador:
    """
    Genera la imagen del grafo a partir de una `Red` y su
    `ResultadoAnalisis`. No recalcula nada: solo dibuja lo ya analizado.
    """

    def __init__(self, red: Red, resultado: ResultadoAnalisis) -> None:
        self.red = red
        self.resultado = resultado
        self.grafo: nx.DiGraph = red.grafo

    # ------------------------------------------------------------------ #
    # Disposición de los nodos
    # ------------------------------------------------------------------ #

    def _posiciones(self) -> dict[str, tuple[float, float]]:
        """
        Layout multipartito: cada nodo se asigna a la columna = índice de
        su generación topológica. Así el grafo se lee por fases de
        izquierda a derecha y las actividades paralelas quedan alineadas
        verticalmente en la misma columna.
        """
        capa: dict[str, int] = {}
        for indice, generacion in enumerate(self.resultado.generaciones):
            for nodo in generacion:
                capa[nodo] = indice
        nx.set_node_attributes(self.grafo, capa, name="capa")
        # align="vertical": cada subconjunto en una vertical, fases en x.
        return nx.multipartite_layout(self.grafo, subset_key="capa", align="vertical")

    # ------------------------------------------------------------------ #
    # Estilos por nodo
    # ------------------------------------------------------------------ #

    def _color_de(self, nodo: str) -> str:
        """Color de relleno según el rol estructural (con prioridad)."""
        if nodo in self.resultado.iniciales:
            return _COLOR_FUENTE
        if nodo in self.resultado.finales:
            return _COLOR_SUMIDERO
        if nodo in self.resultado.nodos_criticos:
            return _COLOR_CRITICO
        return _COLOR_NORMAL

    def _estilo_bordes(self) -> tuple[list[str], list[float]]:
        """
        Borde de cada nodo: morado y grueso si es punto de articulación
        (cuello de botella estructural fuerte); gris fino en caso normal.
        """
        colores: list[str] = []
        anchos: list[float] = []
        articulacion = set(self.resultado.puntos_articulacion)
        for nodo in self.grafo.nodes:
            if nodo in articulacion:
                colores.append(_BORDE_ARTICULACION)
                anchos.append(3.0)
            else:
                colores.append("#37474f")
                anchos.append(1.0)
        return colores, anchos

    def _etiquetas(self) -> dict[str, str]:
        """Etiqueta de cada nodo: id y su centralidad σ(v)."""
        sigma = self.resultado.centralidad
        return {n: f"{n}\nσ={sigma.get(n, 0)}" for n in self.grafo.nodes}

    # ------------------------------------------------------------------ #
    # Generación de la imagen
    # ------------------------------------------------------------------ #

    def generar(self, ruta_salida: str | Path = "outputs/grafo_red.png") -> Path:
        """
        Dibuja el grafo y lo guarda como PNG. Devuelve la ruta del archivo.
        Crea la carpeta de salida si no existe.
        """
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)

        posiciones = self._posiciones()
        colores_nodo = [self._color_de(n) for n in self.grafo.nodes]
        colores_borde, anchos_borde = self._estilo_bordes()

        # Lienzo proporcional al número de fases y a la fase más ancha.
        n_fases = max(len(self.resultado.generaciones), 1)
        max_ancho = max((len(g) for g in self.resultado.generaciones), default=1)
        figura, eje = plt.subplots(
            figsize=(max(10, 1.7 * n_fases), max(6, 1.6 * max_ancho))
        )

        nx.draw_networkx_edges(
            self.grafo,
            posiciones,
            ax=eje,
            arrows=True,
            arrowstyle="-|>",
            arrowsize=16,
            edge_color="#78909c",
            width=1.4,
            node_size=2000,
            connectionstyle="arc3,rad=0.05",
        )
        nx.draw_networkx_nodes(
            self.grafo,
            posiciones,
            ax=eje,
            node_color=colores_nodo,
            edgecolors=colores_borde,
            linewidths=anchos_borde,
            node_size=2000,
        )
        nx.draw_networkx_labels(
            self.grafo,
            posiciones,
            ax=eje,
            labels=self._etiquetas(),
            font_size=9,
            font_color="#102027",
            font_weight="bold",
        )

        criticos = ", ".join(self.resultado.nodos_criticos)
        eje.set_title(
            f"Red estructural — {self.red.nombre_proyecto}\n"
            f"V* (críticos, σ máx={self.resultado.sigma_maximo}): {criticos}   "
            f"|   {self.resultado.numero_de_caminos} caminos fuente→sumidero",
            fontsize=12,
        )
        eje.legend(
            handles=[
                Patch(facecolor=_COLOR_FUENTE, edgecolor="#37474f", label="Fuente (inicial)"),
                Patch(facecolor=_COLOR_SUMIDERO, edgecolor="#37474f", label="Sumidero (final)"),
                Patch(facecolor=_COLOR_CRITICO, edgecolor="#37474f", label="Crítico V* = argmax σ(v)"),
                Patch(facecolor=_COLOR_NORMAL, edgecolor="#37474f", label="Intermedia"),
                Line2D(
                    [0], [0], marker="o", color="w", label="Punto de articulación",
                    markerfacecolor=_COLOR_NORMAL, markeredgecolor=_BORDE_ARTICULACION,
                    markeredgewidth=3, markersize=14,
                ),
            ],
            loc="lower center",
            ncol=3,
            fontsize=9,
            framealpha=0.9,
        )
        eje.set_axis_off()
        figura.tight_layout()
        figura.savefig(ruta_salida, dpi=150, bbox_inches="tight")
        plt.close(figura)  # liberar memoria: no dejamos figuras abiertas
        return ruta_salida
