"""Compatibility path for :mod:`inklet.volume`.

This module moved to ``inklet.volume`` in Inklet 4.3. Import from there;
this path re-exports the same objects and keeps working.
"""
from inklet.volume._contours import (  # noqa: F401
    dataclass, field, i, LabelContour, math, PathPrim, SampledSection,
    Subpath, Vec2, _numpy, _positive, _runs,
)
