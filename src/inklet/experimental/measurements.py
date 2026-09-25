"""Compatibility path for :mod:`inklet.volume`.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.volume` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.volume._measurements import (  # noqa: F401
    BoxRegion,
    LabelMeasurements,
    measure_labels,
    SampledSection,
    Volume,
    _numpy,
    _region,
)

_moved_module(__name__, 'inklet.volume')
