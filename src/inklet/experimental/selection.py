"""Keyed tables and selection states; moved to `inklet.selection` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.selection` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.selection import (  # noqa: F401
    KeyedTable,
    RebasedSelection,
    SCHEMA,
    SelectionState,
    _ids,
    _name,
)

_moved_module(__name__, 'inklet.selection')
