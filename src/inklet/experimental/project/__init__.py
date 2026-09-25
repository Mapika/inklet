"""Figure projects; moved to `inklet.project` in 4.3.

This path keeps working and re-exports the same objects. New code should
import from `inklet.project`.
"""
from . import assets, identity  # noqa: F401
from inklet.project import (  # noqa: F401
    Asset,
    AssetManifest,
    EntityMap,
    ExportDriftWarning,
    FigureProject,
    LayoutEditor,
    Path,
    SCHEMA,
    _name,
    _targets,
    hashlib,
    json,
    os,
    shutil,
    tempfile,
)

__all__ = ['Asset', 'AssetManifest', 'EntityMap', 'FigureProject']
