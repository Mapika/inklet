"""Optional accelerators for the 3D pipeline, imported at call time.

Nothing in `inklet.three` needs a dependency. `inklet.solid("cube", width=20)` runs
on the standard library alone, and that is a property worth defending: the
whole reason to hand-write a hidden-line renderer instead of shelling out to
Blender is that a figure should build on a cluster node with no display, no
package manager and no network.

What the optional pieces buy, when they happen to be there:

``trimesh``
    Formats this package does not parse (GLTF, COLLADA, 3MF, OFF) and mesh
    repair -- welding duplicate vertices and making the winding consistent.
    Both the silhouette test and the shading read the sign of a face normal,
    so repair is worth real money on anything downloaded.
``numpy``
    One stage of the built-in renderer, and only one: the separating-axis test
    the exact painting order asks of every candidate facet pair
    (`order._which_overlap`). That stage vectorises because the question is the
    same for every pair and the answer is a bit, so a whole run goes through as
    arrays and comes back as a mask -- 344,000 pairs on the 18000-face cortical
    surface, and the sort falls from 0.92 s to 0.59 s. The array path and the
    scalar one are held to bit-for-bit equality by
    `tests/test_three_order_vector.py`, which is the condition on using an
    accelerator at all: the same figure on a machine with numpy and a machine
    without must be the same bytes, or it is not reproducible.

    Nothing else in the renderer uses it, and that is measured rather than an
    oversight. On the same surface numpy computes all the face normals in 1.8
    ms against pure Python's 24.2 ms -- and then costs 4.4 ms to marshal the
    vertices in and 12.7 ms to turn the rows back into `Vec3` objects, for 19
    ms all in. A 1.3x win on a stage that is not the problem, and the stages
    that dominate the profile (`hlr.crossings`, `hlr.hides`) walk per-segment
    candidate lists of varying length, which is the shape numpy is worst at.
    Getting a general speedup would mean arrays all the way through the
    pipeline: a different renderer, not an accelerator, and one that belongs
    behind `register_backend` rather than inside this one. The optional Blender
    backend also uses numpy, through `have()`, for raster tracing.

Mirrors `inklet.assets.deps` deliberately. Two modules that solve the same problem
two different ways is one more thing for the next person to learn.
"""

from __future__ import annotations

import importlib
import shutil
from types import ModuleType

__all__ = ["require", "have", "have_binary", "MissingDependency", "THREE_EXTRA"]

THREE_EXTRA = 'pip install "inklet[three]"'

_PURPOSE = {
    "numpy": "the array separating-axis test in the exact painting order, and "
             "raster tracing in the Blender backend",
    "trimesh": "reading GLTF/COLLADA/3MF and repairing mesh winding",
}


class MissingDependency(ImportError):
    """An optional dependency is needed for this path and is not installed."""


def require(module: str) -> ModuleType:
    """Import an optional dependency, or explain what it was wanted for."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        package = module.split(".")[0]
        raise MissingDependency(
            f"{module} is needed for {_PURPOSE.get(package, 'this feature')} "
            f"and is not installed; {THREE_EXTRA}"
        ) from exc


def have(module: str) -> bool:
    """Whether an optional dependency can be imported.

    Used to *widen* what works, never to change what a working path produces.
    A figure that renders differently depending on what is installed is a
    figure you cannot reproduce, so every caller of this either adds a format
    or picks an arithmetic route to an identical answer.
    """
    try:
        importlib.import_module(module)
    except ImportError:
        return False
    return True


def have_binary(name: str) -> bool:
    return shutil.which(name) is not None
