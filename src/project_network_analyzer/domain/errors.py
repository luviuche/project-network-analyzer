"""Domain errors.

A single exception type for everything the domain rejects, so callers —
the CLI today, an HTTP exception handler tomorrow — only have to catch
one thing.
"""

from __future__ import annotations


class NetworkStructureError(Exception):
    """The network breaks one of the model's structural constraints."""
