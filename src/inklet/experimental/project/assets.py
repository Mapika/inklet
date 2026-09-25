"""Project asset inventories; moved to `inklet.project.assets` in 4.3.

This path keeps working and re-exports the same objects. New code should
import from `inklet.project.assets`.
"""
from inklet.project.assets import (  # noqa: F401
    Asset,
    AssetManifest,
    Path,
    PurePosixPath,
    asdict,
    dataclass,
    digest,
    file_at,
    hashlib,
    name,
    re,
    relative_path,
)
