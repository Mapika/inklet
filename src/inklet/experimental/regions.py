"""Compatibility path for :mod:`inklet.volume`.

This module moved to ``inklet.volume`` in Inklet 4.3. Import from there;
this path re-exports the same objects and keeps working.
"""
from inklet.volume._regions import (  # noqa: F401
    BoxRegion, dataclass, i, itertools, math, Plane, Volume, _numpy,
    _positive, _snapshot, _UNITS, _vector,
)
