"""Compatibility path for :mod:`inklet.volume`.

This module moved to ``inklet.volume`` in Inklet 4.3. Import from there;
this path re-exports the same objects and keeps working.
"""
from inklet.volume._sections import (  # noqa: F401
    dataclass, i, ImagePrim, io, math, Plane, reslice, SampledSection,
    Volume, _numpy, _positive, _snapshot, _UNITS, _vector,
)
