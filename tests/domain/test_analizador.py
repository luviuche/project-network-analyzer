"""
Pruebas de analizador.py — análisis estructural del DAG.

Cubren: orden topológico válido y determinista, conteo y forma de los
caminos fuente→sumidero, centralidad σ(v) (DP contrastada con la
enumeración exhaustiva), nodos críticos V*, cuellos de botella, puntos
de articulación, clasificación, generaciones (anticadenas) y el límite
de seguridad de la enumeración.
"""

from collections import Counter
from pathlib import Path

import pytest

from project_network_analyzer.domain.analizador import Analizador, ResultadoAnalisis
from project_network_analyzer.domain.modelo import ErrorEstructuraRed, Red

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"

# Valores esperados para el caso de prueba (calculados a mano y por DP).
SIGMA_ESPERADO = {
    "A": 12, "B": 12, "C": 9, "D": 3, "E": 3, "F": 6, "G": 6, "H": 6,
    "I": 8, "J": 4, "K": 8, "L": 8, "M": 4, "N": 12, "O": 12,
}


@pytest.fixture
def analizador() -> Analizador:
    return Analizador(Red.desde_json(DATOS))


@pytest.fixture
def resultado(analizador) -> ResultadoAnalisis:
    return analizador.analizar()


# --------------------------------------------------------------------- #
# Orden topológico
# --------------------------------------------------------------------- #


def test_orden_topologico_es_valido(analizador):
    orden = analizador.orden_topologico()
    pos = {n: i for i, n in enumerate(orden)}
    for u, v in analizador.grafo.edges:
        assert pos[u] < pos[v], f"arista {u}->{v} viola el orden topológico"


def test_orden_topologico_es_determinista(analizador):
    assert analizador.orden_topologico() == analizador.orden_topologico()


# --------------------------------------------------------------------- #
# Caminos fuente → sumidero
# --------------------------------------------------------------------- #


def test_numero_de_caminos(analizador):
    assert analizador.numero_de_caminos() == 12


def test_caminos_son_validos(analizador):
    caminos, truncado = analizador.caminos_fuente_sumidero()
    assert not truncado
    assert len(caminos) == 12
    fuentes, sumideros = set(analizador.red.fuentes), set(analizador.red.sumideros)
    for camino in caminos:
        assert camino[0] in fuentes
        assert camino[-1] in sumideros
        for u, v in zip(camino, camino[1:]):
            assert analizador.grafo.has_edge(u, v)


def test_limite_de_enumeracion_trunca_pero_conteo_es_exacto(analizador):
    caminos, truncado = analizador.caminos_fuente_sumidero(limite=5)
    assert truncado
    assert len(caminos) == 5
    # El conteo por DP no depende de la enumeración: sigue siendo exacto.
    assert analizador.numero_de_caminos() == 12


# --------------------------------------------------------------------- #
# Centralidad σ(v) y nodos críticos
# --------------------------------------------------------------------- #


def test_centralidad_valores_exactos(analizador):
    assert analizador.centralidad_de_paso() == SIGMA_ESPERADO


def test_centralidad_dp_coincide_con_enumeracion(analizador):
    """σ(v) por DP == nº de caminos enumerados que contienen v."""
    sigma = analizador.centralidad_de_paso()
    caminos, _ = analizador.caminos_fuente_sumidero()
    conteo = Counter()
    for camino in caminos:
        for nodo in camino:
            conteo[nodo] += 1
    assert sigma == dict(conteo)


def test_nodos_criticos(analizador):
    criticos, maximo = analizador.nodos_criticos()
    assert criticos == ["A", "B", "N", "O"]
    assert maximo == 12


# --------------------------------------------------------------------- #
# Cuellos de botella y puntos de articulación
# --------------------------------------------------------------------- #


def test_cuellos_de_botella(analizador):
    # σ(v) == nº total de caminos -> pasan todos los caminos por v.
    assert analizador.cuellos_de_botella() == ["A", "B", "N", "O"]


def test_puntos_de_articulacion(analizador):
    # A y O son obligatorios pero de grado 1: no desconectan la red.
    assert analizador.puntos_articulacion() == ["B", "N"]


# --------------------------------------------------------------------- #
# Clasificación y paralelismo
# --------------------------------------------------------------------- #


def test_clasificacion(analizador):
    clases = analizador.clasificar_actividades()
    assert clases["iniciales"] == ["A"]
    assert clases["finales"] == ["O"]
    assert set(clases["intermedias"]) == set("BCDEFGHIJKLMN")
    assert "A" not in clases["intermedias"] and "O" not in clases["intermedias"]


def test_generaciones_son_anticadenas(analizador):
    """Dentro de una misma generación no puede haber aristas."""
    generaciones = analizador.generaciones()
    assert generaciones[0] == ["A"]
    assert generaciones[-1] == ["O"]
    for gen in generaciones:
        for u in gen:
            for v in gen:
                assert not analizador.grafo.has_edge(u, v)


def test_pares_paralelos(analizador):
    pares = set(analizador.pares_paralelos())
    assert ("C", "E") in pares          # ambos dependen de B, incomparables
    assert ("A", "O") not in pares      # A alcanza O: son comparables


# --------------------------------------------------------------------- #
# Resultado agregado y casos límite
# --------------------------------------------------------------------- #


def test_analizar_resultado_consistente(resultado):
    assert isinstance(resultado, ResultadoAnalisis)
    assert resultado.numero_de_caminos == 12
    assert resultado.nodos_criticos == ["A", "B", "N", "O"]
    assert resultado.sigma_maximo == 12
    assert not resultado.caminos_truncados
    assert "Orden topológico" in resultado.resumen()


def test_analizador_rechaza_grafo_ciclico():
    r = Red("ciclica")
    for n in ("X", "Y"):
        r.agregar_actividad(n, n)
    r.agregar_precedencia("X", "Y")
    r.agregar_precedencia("Y", "X")
    with pytest.raises(ErrorEstructuraRed):
        Analizador(r)
