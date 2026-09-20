"""
cargador.py — Lectura de redes desde disco (Grupo 6).

Único punto del proyecto que lee el JSON del caso. Deserializa y delega
la construcción en `Network.from_dict`, que es pura.

Esta separación es lo que permite que la misma red venga después de un
cuerpo HTTP validado con Pydantic o de una fila de PostgreSQL: cambia el
adaptador, no el dominio.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.domain.network import Network


def cargar_red(ruta: str | Path) -> Network:
    """
    Construye una `Network` a partir de un archivo JSON.

    Si el fichero no existe se lanza `NetworkStructureError`, para que quien
    llama solo tenga que manejar el error propio del proyecto. Si el
    nombre del proyecto no viene en los datos, se usa el nombre del
    fichero.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise NetworkStructureError(f"No se encontró el archivo: {ruta}")

    with ruta.open(encoding="utf-8") as f:
        datos = json.load(f)

    return Network.from_dict(datos, default_name=ruta.stem)
