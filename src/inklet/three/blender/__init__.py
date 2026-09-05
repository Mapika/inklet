"""Line art from Blender, for meshes a pure-Python renderer will not do justice.

A 70 000-triangle scan or a CAD assembly is not a hidden-line problem you want
to solve twice. Blender's Grease Pencil Line Art already solves it, exactly and
fast, so this package drives Blender as a subprocess and reads the vector
result back into millimetres:

    from inklet.three.blender import line_art, LineArtOptions

    drawing = line_art("bunny.obj", width=48, camera="isometric")
    drawing.polylines    # strokes, origin-centred mm, y downward
    drawing.silhouette   # the outer outline as a closed polygon

Blender is strictly optional and is never imported: `import inklet` works on a
machine that has never heard of it, and the first bake is what goes looking.
`blender_available()` answers whether it is there, and `find_blender()` raises
a sentence naming `INKLET_BLENDER` when it is not.

The camera is `inklet.three.camera.Camera` -- the same presets, the same azimuth
and elevation, the same `look_at` -- so a figure can be drawn with the builtin
renderer while it is being composed and re-drawn through Blender for the final
version without changing a line of it.

The five pieces, in the order a bake goes through them: `discover` finds the
binary, `options` says what to draw, `script` writes a program for Blender's
own interpreter, `svgread` turns what comes back into geometry, and `outline`
recovers the closed silhouette that arrows clip against.
"""

from __future__ import annotations

from .discover import (
    ENV_VAR, MINIMUM_VERSION, Blender, BlenderError, BlenderNotFound,
    BlenderTooOld, blender_available, find_blender,
)
from .lineart import (
    DEFAULT_MARGIN, DEFAULT_RESOLUTION, DEFAULT_TIMEOUT, LINES_LAYER,
    SILHOUETTE_LAYER, LineArtDrawing, bake_svg, cache_key, camera_spec,
    line_art, page_up,
)
from .options import (
    DEFAULT_CREASE_DEGREES, FITS, UP_AXES, LineArtOptions,
)
from .tracing import CHAINED, HULL, TRACED, outline
from .script import SCRIPT_VERSION, build_script
from .svgread import GreasePencilSvg, Layer, place_layers, read_gpencil_svg

__all__ = [
    "line_art", "LineArtDrawing", "LineArtOptions",
    "blender_available", "find_blender", "Blender",
    "BlenderError", "BlenderNotFound", "BlenderTooOld",
    "FITS", "UP_AXES", "ENV_VAR", "MINIMUM_VERSION", "DEFAULT_CREASE_DEGREES",
    "read_gpencil_svg", "place_layers", "GreasePencilSvg", "Layer",
    "build_script", "SCRIPT_VERSION", "bake_svg", "cache_key", "camera_spec",
    "page_up", "outline", "TRACED", "CHAINED", "HULL",
    "LINES_LAYER", "SILHOUETTE_LAYER", "DEFAULT_RESOLUTION", "DEFAULT_TIMEOUT",
    "DEFAULT_MARGIN",
]
