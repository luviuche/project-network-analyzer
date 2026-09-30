"""
loader.py — Reading networks from disk.

The only place in the project that reads the case JSON. It deserialises
and hands construction to `Network.from_dict`, which is pure.

This split is what lets the same network arrive later from a Pydantic
validated HTTP body or a PostgreSQL row: the adapter changes, the domain
does not.
"""

from __future__ import annotations

import json
from pathlib import Path

from project_network_analyzer.domain.errors import NetworkStructureError
from project_network_analyzer.domain.network import Network


def load_network(path: str | Path) -> Network:
    """
    Build a `Network` from a JSON file.

    Every way the file itself can be unusable — missing, not UTF-8, not
    valid JSON, not a JSON object — raises `NetworkStructureError`, so
    callers only ever have to handle the project's own error. When the
    data carries no project name, the file name is used.
    """
    path = Path(path)
    if not path.is_file():
        raise NetworkStructureError(f"File not found: {path}")

    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except UnicodeDecodeError:
        raise NetworkStructureError(f"The file is not UTF-8 text: {path}") from None
    except json.JSONDecodeError as e:
        raise NetworkStructureError(
            f"The file is not valid JSON: {path} "
            f"(line {e.lineno}, column {e.colno}: {e.msg})."
        ) from None

    if not isinstance(data, dict):
        raise NetworkStructureError(
            f"The file must hold a JSON object with an 'activities' list: {path}"
        )

    return Network.from_dict(data, default_name=path.stem)
