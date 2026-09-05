"""Optional image dependencies, imported at call time rather than at import.

`import inklet` has to keep working in an environment with no image stack at all:
the library's job is geometry, and a scientist who only draws boxes should not
pay for Pillow, let alone for a 200 MB ONNX runtime. So nothing here is
imported at module scope. The first call into an image function is what pulls
the dependency in, and the error a caller gets names the extra to install
instead of surfacing a bare `ModuleNotFoundError` from four frames down.
"""

from __future__ import annotations

import importlib
import shutil
from types import ModuleType

__all__ = [
    "AssetError", "MissingDependency", "require", "have", "have_binary",
    "numpy", "pillow", "IMAGE_EXTRA",
]

IMAGE_EXTRA = 'pip install "inklet[images]"'

# What each optional piece is for and how to get it, so the error a caller sees
# says why the thing is wanted rather than only that it is missing. rembg has
# its own hint because it is deliberately *not* part of the `images` extra.
_PURPOSE = {
    "numpy": "array maths for masks, silhouettes and colour harmonisation",
    "PIL": "reading rasters, blurring and resampling",
    "rembg": "learned background removal for subjects on a busy background",
}

_HINT = {
    "rembg": ("pip install rembg, and warm its model up once outside your "
              "build -- it downloads ~180 MB on first use"),
}


class AssetError(Exception):
    """Anything the asset pipeline cannot do: a missing file, an unreadable
    raster, a backend that is not installed, a cutout that found no subject."""


class MissingDependency(AssetError):
    """An optional dependency is needed and is not installed."""


def require(module: str) -> ModuleType:
    """Import an optional dependency or explain how to get it."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        package = module.split(".")[0]
        purpose = _PURPOSE.get(package, "this feature")
        raise MissingDependency(
            f"{module} is needed for {purpose} and is not installed; "
            f"{_HINT.get(package, IMAGE_EXTRA)}"
        ) from exc


def have(module: str) -> bool:
    """Whether an optional dependency can be imported. Used to choose a default
    backend, never to change output silently -- the chosen backend is recorded
    in the provenance chain."""
    try:
        importlib.import_module(module)
    except ImportError:
        return False
    return True


def have_binary(name: str) -> bool:
    return shutil.which(name) is not None


def numpy() -> ModuleType:
    return require("numpy")


def pillow() -> tuple[ModuleType, ModuleType]:
    """`PIL.Image` and `PIL.ImageFilter`, the only two submodules used here."""
    require("PIL")
    return require("PIL.Image"), require("PIL.ImageFilter")
