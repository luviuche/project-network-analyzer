"""
loader.py — Reading networks from disk.

The only place in the project that reads the case JSON. It deserialises
and hands construction to `Network.from_dict`, which is pure.

This split is what lets the same network arrive later from a Pydantic
validated HTTP body or a PostgreSQL row: the adapter changes, the domain
does not.

Error text is Spanish because it is user-facing output; the identifiers,
docstrings and comments around it are English.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.domain.network import Network


def load_network(path: str | Path) -> Network:
    """
    Build a `Network` from a JSON file.

    A missing file raises `NetworkStructureError`, so callers only ever
    have to handle the project's own error. When the data carries no
    project name, the file name is used.
    """
    path = Path(path)
    if not path.is_file():
        raise NetworkStructureError(f"No se encontró el archivo: {path}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    return Network.from_dict(data, default_name=path.stem)
