"""Compatibility path for :mod:`inklet.volume`.

This module moved to ``inklet.volume`` in Inklet 4.3. Import from there;
this path re-exports the same objects and keeps working.
"""
from inklet.volume._slabs import (  # noqa: F401
    BoxRegion, dataclass, math, Plane, project_slab, replace,
    SampledSection, Slab, SlabProjection, Volume, _numpy, _positive,
    _snapshot, _validate,
)
