"""The layout editor; moved to `inklet.editor` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.editor` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.editor import (  # noqa: F401
    Composition,
    LayoutEditor,
    SCHEMA,
    _EDITORS,
    _expression,
    _placement,
    _targets,
    document,
)

_moved_module(__name__, 'inklet.editor')
