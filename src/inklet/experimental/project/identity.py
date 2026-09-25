"""Project entity maps; moved to `inklet.project.identity` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.project.identity` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.project.identity import (  # noqa: F401
    EntityMap,
    KeyedTable,
    SelectionState,
    _ids,
    name,
)

_moved_module(__name__, 'inklet.project.identity')
