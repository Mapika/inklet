"""Errors raised while compiling documents."""
from __future__ import annotations

from ..core import DiagramError


class LayoutError(DiagramError):
    """A document cannot satisfy its declared physical layout constraints."""
