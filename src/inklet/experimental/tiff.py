"""Compatibility path for :mod:`inklet.volume`.

This module moved to ``inklet.volume`` in Inklet 4.3. Import from there;
this path re-exports the same objects and keeps working.
"""
from inklet.volume._tiff import (  # noqa: F401
    dataclass, ET, hashlib, json, Path, read_tiff, TiffImage, Volume,
    _numpy,
)
