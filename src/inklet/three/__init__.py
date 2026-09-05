"""Real 3D, rendered to vector line art.

A paper figure regularly needs an object in it: a chip, a cortical column, an
exploded assembly, a coordinate frame. Composited as a raster it does not scale,
does not take the theme's colours, and cannot be traced by an arrow.
`inklet.model()` and `inklet.solid()` return a `Diagram` of paths instead -- one that
stacks, restyles, prints at any size, exposes named 3D points as 2D anchors, and
clips arrows on its own silhouette.

    import inklet

    chip = inklet.solid("box", width=26, view="isometric", style="shaded",
                     size_x=1.6, size_z=0.22)
    head = inklet.model("spot.obj", width=34, view="three-quarter")
    bench = inklet.scene([("stage", stage), ("lens", lens)], width=90, view="front")
    frame = inklet.axes(width=18, view="isometric")
    fig.link(inklet.box("probe"), head.at("nose"))

`scene()` is the one to reach for when a figure has more than one object in it:
`model()` fits whatever it is handed to the width it was asked for, so a dozen
calls give a dozen scales, and nothing decides which object is in front.

Everything here runs on the standard library. That is a deliberate,
load-bearing choice: `inklet.solid("cube", width=20)` has to work in a bare
`pip install inklet`, on a cluster node with no display and no network. Optional
pieces widen what is possible without ever being required --

* `trimesh`, when importable, adds GLTF/COLLADA/3MF/OFF and mesh repair.
* `numpy`, when importable, vectorises projection on large meshes.
* other renderers register themselves through `inklet.three.register_backend`;
  the contract they implement is documented in `inklet.three.backend`.

The pipeline, in the order it runs, one module per step:

`parse` / `solids`
    Get a `Mesh`: read one from disk or build one parametrically.
`camera`
    Choose a view and auto-fit the projection to the requested millimetres, so
    the author never computes a scale.
`edges`
    Find the edges worth drawing: silhouette, crease, boundary. This is what
    makes it read as a drawing rather than as a wireframe. Where the mesh
    stands for a smooth surface, the silhouette is taken off that surface
    rather than off the facets.
`hlr`
    Remove the edges the solid hides, cutting each one where it passes under a
    projected triangle and testing the pieces against a spatial grid.
`occlude`
    How enclosed each vertex is, so that a hollow reads as a hollow. Screen
    space, and folded into the tone rather than painted over it.
`shade`
    Optional flat-shaded facets, painter-sorted and tinted from the theme.
`order`
    The painter's order done exactly, for the facets no depth key can rank:
    ask the overlapping pairs, and cut the pairs with no answer.
`backend` / `api`
    Assemble the paths into a node with anchors, a silhouette trace and a name.

`protein` sits beside that pipeline rather than in it: a swept ribbon cartoon
of a protein backbone -- `inklet.cartoon(chain)` -- which hands the steps above a
`Mesh` like any other.
"""

from __future__ import annotations

from .api import (
    DEFAULT_WIDTH, MODEL_KIND, PICKS, SILHOUETTE_KIND, anchor3d, axes, model,
    outline_of, page_scale, parts_of, scene, scene_paint, solid, view_of,
)
# Registers the "blender" backend. Imported for the side effect only; it pulls
# in nothing heavier than the cache helpers, and never `inklet.three.blender`
# itself until a bake or an availability check actually asks for it.
from . import blender_backend as _blender_backend  # noqa: F401
from .backend import (
    CREASE_KIND, FACETS_KIND, INK_KIND, OUTLINE_KIND, SHADINGS, SORTS,
    STYLES, TOON, Look, Rendering, Request, available_backends, backends,
    register_backend, render,
)
from .camera import PRESETS, Camera, Projected, View, preset_names
from .depth import DepthField, ScenePaint, depth_field
from .edges import (
    BOUNDARY, CREASE, DEFAULT_CREASE_DEGREES, SILHOUETTE, SMOOTH_CEILING,
    FeatureEdge, Smoothed, chain_edges, facing_faces, feature_edges,
    smooth_silhouette,
)
from .hlr import Occluders, VisibleRun, visible_runs
from .linalg import Mat4, Vec3
from .drill import DEFAULT_HOLE_SEGMENTS, drill, subtract
from .mesh import Mesh, MeshError, merge
from .occlude import vertex_occlusion
from .order import painter_sort
from .parse import NATIVE_FORMATS, load, sniff, supported_formats
from .place import AXES, as_axis, placement
from .protein import (
    Chain, Residue, Station, cartoon, ribbon, sides_for, stations, steps_for,
)
from .shade import (AUTO_EXACT_FACETS, AUTO_EXACT_PAIRS, DEFAULT_LIGHT, Facet,
                    sorted_facets, sorts_exactly)
from .solids import (
    DEFAULT_TOLERANCE, ROUND_FLOOR, SOLIDS, build, segments_for, solid_names,
    subdivisions_for, sweep, tessellation,
)

__all__ = [
    # authoring
    "model", "solid", "scene", "axes", "anchor3d", "view_of",
    "outline_of", "parts_of", "scene_paint", "ScenePaint",
    "MODEL_KIND", "SILHOUETTE_KIND", "DEFAULT_WIDTH", "PICKS",
    # geometry
    "Mesh", "MeshError", "merge", "Vec3", "Mat4",
    "drill", "subtract", "DEFAULT_HOLE_SEGMENTS",
    "placement", "as_axis", "AXES",
    "load", "sniff", "supported_formats", "NATIVE_FORMATS",
    "build", "solid_names", "SOLIDS", "sweep",
    "page_scale", "tessellation", "segments_for", "subdivisions_for",
    "DEFAULT_TOLERANCE", "ROUND_FLOOR",
    # the protein cartoon. Its constants -- SIDES, STEPS, SECTIONS, the DSSP
    # letters -- stay in `inklet.three.protein`: `inklet.three.HELIX` would be a
    # claim about the whole 3D layer that only the cartoon means.
    "cartoon", "ribbon", "stations", "sides_for", "steps_for", "Station",
    "Residue", "Chain",
    # viewing
    "Camera", "View", "Projected", "PRESETS", "preset_names",
    # the drawing pipeline
    "FeatureEdge", "feature_edges", "facing_faces", "chain_edges",
    "SILHOUETTE", "CREASE", "BOUNDARY", "DEFAULT_CREASE_DEGREES",
    "smooth_silhouette", "Smoothed", "SMOOTH_CEILING",
    "visible_runs", "VisibleRun", "Occluders",
    "sorted_facets", "sorts_exactly", "AUTO_EXACT_FACETS", "AUTO_EXACT_PAIRS",
    "Facet", "DEFAULT_LIGHT", "painter_sort",
    "vertex_occlusion", "depth_field", "DepthField",
    # backends
    "register_backend", "backends", "available_backends", "render",
    "Look", "Request", "Rendering", "STYLES", "SHADINGS", "SORTS", "TOON",
    "INK_KIND", "FACETS_KIND", "OUTLINE_KIND", "CREASE_KIND",
]
