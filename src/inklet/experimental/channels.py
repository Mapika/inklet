"""Compatibility path for :mod:`inklet.volume`.

This module moved to ``inklet.volume`` in Inklet 4.3. Import from there;
this path re-exports the same objects and keeps working.
"""
from inklet.volume._channels import (  # noqa: F401
    Channel, Composite, dataclass, i, ImagePrim, io, math, parse_color,
    SampledSection, SlabProjection, to_hex, _geometry, _numpy, _positive,
    _snapshot,
)
