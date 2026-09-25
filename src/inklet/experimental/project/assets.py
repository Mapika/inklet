"""Project asset inventories; moved to `inklet.project.assets` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Import from `inklet.project.assets` instead; the objects are the same.
"""
from inklet._compat import moved_module as _moved_module
from inklet.project.assets import (  # noqa: F401
    Asset,
    AssetManifest,
    digest,
    file_at,
    name,
    relative_path,
)

_moved_module(__name__, 'inklet.project.assets')
