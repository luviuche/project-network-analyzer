"""
Pruebas de infrastructure/cargador.py — lectura de redes desde disco.

Es la única capa que toca el sistema de archivos, así que aquí viven las
pruebas que necesitan ficheros reales (`tmp_path`). El dominio se prueba
con diccionarios, en `tests/domain/test_modelo.py`.
"""

import json
from pathlib import Path

import pytest

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.infrastructure.cargador import cargar_red

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "proyecto_software.json"


def test_cargar_el_caso_de_prueba_real():
    red = cargar_red(DATOS)
    assert len(red) == 15
    assert red.graph.number_of_edges() == 20
    assert red.project_name.startswith("Desarrollo de Aplicación Web")


def test_cargar_acepta_una_ruta_en_texto():
    assert len(cargar_red(str(DATOS))) == 15


def test_archivo_inexistente_lanza_error_del_dominio():
    """Quien llama solo debe tener que manejar NetworkStructureError."""
    with pytest.raises(NetworkStructureError):
        cargar_red(RAIZ / "data" / "no_existe.json")


def test_sin_nombre_de_proyecto_usa_el_nombre_del_fichero(tmp_path):
    datos = {"actividades": [{"id": "A", "nombre": "a", "precedentes": []}]}
    ruta = tmp_path / "mi-proyecto.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")

    assert cargar_red(ruta).project_name == "mi-proyecto"
