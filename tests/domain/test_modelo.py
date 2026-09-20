"""
Pruebas de modelo.py — clase Red y validaciones estructurales.

Cubren: construcción desde JSON e independencia del orden, accesores
deterministas, las cuatro restricciones del modelo (aciclicidad,
conectividad débil, fuente, sumidero) y los errores propios
(`ErrorEstructuraRed`).
"""

import json
from pathlib import Path

import pytest

from project_network_analyzer.domain.modelo import ErrorEstructuraRed, Red, ResultadoValidacion

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def red_software() -> Red:
    """Red construida desde el caso de prueba real (15 actividades)."""
    return Red.desde_json(DATOS)


@pytest.fixture
def red_cadena() -> Red:
    """DAG mínimo válido: A → B → C (fuente A, sumidero C)."""
    r = Red("cadena")
    for n in ("A", "B", "C"):
        r.agregar_actividad(n, f"act-{n}")
    r.agregar_precedencia("A", "B")
    r.agregar_precedencia("B", "C")
    return r


# --------------------------------------------------------------------- #
# Construcción desde JSON
# --------------------------------------------------------------------- #


def test_desde_json_estructura_basica(red_software):
    assert len(red_software) == 15
    assert red_software.grafo.number_of_edges() == 20
    assert red_software.actividades == list("ABCDEFGHIJKLMNO")
    assert red_software.nombre_proyecto.startswith("Desarrollo de Aplicación Web")


def test_desde_json_fuente_y_sumidero_unicos(red_software):
    assert red_software.fuentes == ["A"]
    assert red_software.sumideros == ["O"]


def test_nombre_de_devuelve_nombre_legible(red_software):
    assert red_software.nombre_de("A") == "Levantamiento de requisitos"
    with pytest.raises(ErrorEstructuraRed):
        red_software.nombre_de("ZZZ")


def test_desde_json_independiente_del_orden(tmp_path):
    """Una actividad puede declararse antes que su precedente en el JSON."""
    datos = {
        "proyecto": {"nombre": "orden"},
        "actividades": [
            {"id": "B", "nombre": "b", "precedentes": ["A"]},
            {"id": "A", "nombre": "a", "precedentes": []},
        ],
    }
    ruta = tmp_path / "p.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    red = Red.desde_json(ruta)
    assert red.precedencias == [("A", "B")]
    assert red.fuentes == ["A"] and red.sumideros == ["B"]


def test_desde_json_archivo_inexistente():
    with pytest.raises(ErrorEstructuraRed):
        Red.desde_json(RAIZ / "data" / "no_existe.json")


def test_desde_json_sin_actividades(tmp_path):
    ruta = tmp_path / "vacio.json"
    ruta.write_text(json.dumps({"actividades": []}), encoding="utf-8")
    with pytest.raises(ErrorEstructuraRed):
        Red.desde_json(ruta)


# --------------------------------------------------------------------- #
# Validaciones estructurales (restricciones del modelo)
# --------------------------------------------------------------------- #


def test_red_valida(red_software):
    v = red_software.validar()
    assert isinstance(v, ResultadoValidacion)
    assert v.es_valida
    assert v.es_aciclico and v.es_debilmente_conexo
    assert v.fuentes == ["A"] and v.sumideros == ["O"]
    assert v.ciclo_detectado == []


def test_cadena_minima_es_valida(red_cadena):
    assert red_cadena.validar().es_valida


def test_deteccion_de_ciclo():
    r = Red("ciclica")
    for n in ("X", "Y", "Z"):
        r.agregar_actividad(n, n)
    r.agregar_precedencia("X", "Y")
    r.agregar_precedencia("Y", "Z")
    r.agregar_precedencia("Z", "X")

    assert not r.es_aciclico()
    ciclo = r.detectar_ciclo()
    assert ciclo[0] == ciclo[-1]               # el ciclo se cierra
    assert set("XYZ").issubset(set(ciclo))

    v = r.validar()
    assert not v.es_valida
    assert not v.es_aciclico
    assert v.ciclo_detectado == ciclo


def test_no_debilmente_conexa():
    """Dos componentes desconectadas: A→B y C→D."""
    r = Red("desconexa")
    for n in ("A", "B", "C", "D"):
        r.agregar_actividad(n, n)
    r.agregar_precedencia("A", "B")
    r.agregar_precedencia("C", "D")

    v = r.validar()
    assert v.es_aciclico
    assert not v.es_debilmente_conexo
    assert not v.es_valida


def test_grafo_vacio_no_es_valido():
    r = Red("vacia")
    v = r.validar()
    assert not v.es_debilmente_conexo
    assert not v.es_valida


def test_exigir_valida():
    r = Red("ciclica")
    for n in ("X", "Y"):
        r.agregar_actividad(n, n)
    r.agregar_precedencia("X", "Y")
    r.agregar_precedencia("Y", "X")
    with pytest.raises(ErrorEstructuraRed):
        r.exigir_valida()


def test_exigir_valida_devuelve_resultado(red_cadena):
    v = red_cadena.exigir_valida()
    assert isinstance(v, ResultadoValidacion) and v.es_valida


# --------------------------------------------------------------------- #
# Errores de construcción
# --------------------------------------------------------------------- #


def test_actividad_duplicada():
    r = Red("t")
    r.agregar_actividad("A", "a")
    with pytest.raises(ErrorEstructuraRed):
        r.agregar_actividad("A", "otra")


def test_precedente_inexistente():
    r = Red("t")
    r.agregar_actividad("A", "a")
    with pytest.raises(ErrorEstructuraRed):
        r.agregar_precedencia("NO_EXISTE", "A")


def test_auto_precedencia_prohibida():
    r = Red("t")
    r.agregar_actividad("A", "a")
    with pytest.raises(ErrorEstructuraRed):
        r.agregar_precedencia("A", "A")


# --------------------------------------------------------------------- #
# Utilidades / representación
# --------------------------------------------------------------------- #


def test_resumen_validacion_contiene_estado(red_software):
    texto = red_software.validar().resumen()
    assert "VÁLIDA" in texto
    assert "Fuentes" in texto and "Sumideros" in texto


def test_len_y_repr(red_software):
    assert len(red_software) == 15
    assert "|V|=15" in repr(red_software)
    assert "|E|=20" in repr(red_software)
