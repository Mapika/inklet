"""Compatibility path for :mod:`inklet.volume`.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.volume` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.volume._sections import (  # noqa: F401
    i,
    ImagePrim,
    Plane,
    reslice,
    SampledSection,
    Volume,
    _numpy,
    _positive,
    _snapshot,
    _UNITS,
    _vector,
)

_moved_module(__name__, 'inklet.volume')
