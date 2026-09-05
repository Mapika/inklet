"""The public geometry layer: paths, arcs, markers, and explicit placement.

Core has had bezier-capable paths since M1 and nothing outside `inklet.links`
could reach them, which is why the library could draw a node-link diagram and
not a scatter plot. This package is the door. It adds no geometry core lacks;
it makes core's geometry expressible, in millimetres, through the same
conventions as the rest of `inklet` -- centred on the origin, styled by keyword,
returning a `Diagram` that stacks, frames, rotates and gets traced like a box.

    import inklet

    inklet.polygon([(0, 0), (10, 0), (5, 8)], fill="#eee")
    inklet.curve([(0, 0), (10, -4), (20, 2)], smooth=0.5)
    inklet.sector(12, -90, -18, inner=6)
    inklet.place([((3, 4), inklet.marker("circle", 1.5))])
"""

from .annotate import (
    ANNOTATION_KIND, BRACKET_KIND, DIMENSION_KIND, LABEL_SPEC_NOTE,
    LETTER_KIND, SCALEBAR_KIND, ANNOTATE_SIDES, LabelSpec,
    annotate, annotation_side, bracket, dimension, label_slot, label_specs,
    letters, scalebar,
)
from .clip import (
    CLIP_KIND, area_within, clip, clip_polygon, clip_polyline, polygon_area,
)
from .coords import (
    AREA_NOTE, ORIGIN_ANCHOR, Point, as_drawn, declare_area, placed_anchor,
    plot_area, to_point, to_points,
)
from .path import (
    ENCODED_KIND_SUFFIX, FLATTEN_STEPS, catmull_rom, curve, encoded,
    is_encoded_kind, path, polygon, polyline,
)
from .place import drawn, place
from .shapes import MARKER_KINDS, arc, arc_cubics, marker, sector

__all__ = [
    "path", "polyline", "polygon", "curve", "arc", "sector", "marker", "place",
    "drawn", "placed_anchor",
    "annotate", "annotation_side", "bracket", "dimension", "letters",
    "scalebar", "label_slot", "label_specs", "LabelSpec",
    "ANNOTATION_KIND", "BRACKET_KIND", "DIMENSION_KIND",
    "SCALEBAR_KIND", "ANNOTATE_SIDES", "LABEL_SPEC_NOTE", "LETTER_KIND",
    "clip", "clip_polygon", "clip_polyline", "CLIP_KIND",
    "area_within", "polygon_area",
    "as_drawn", "to_point", "to_points", "catmull_rom", "arc_cubics",
    "plot_area", "declare_area", "AREA_NOTE",
    "MARKER_KINDS", "ORIGIN_ANCHOR", "FLATTEN_STEPS", "Point",
    "encoded", "is_encoded_kind", "ENCODED_KIND_SUFFIX",
]
