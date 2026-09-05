"""Core geometry and the diagram tree. No fonts, no rendering, no I/O."""

from .diagram import (
    AnchorRef, Diagram, DiagramError, Placement, RenderItem,
    flatten, group, note_through, resolve, world_point,
)
from .envelope import Envelope
from .geom import EAST, IDENTITY, NORTH, ORIGIN, SOUTH, WEST, Affine, Rect, Vec2
from .prims import (
    FILL_RULES, EllipsePrim, ImagePrim, PathPrim, PhantomPrim, Prim, RectPrim,
    Subpath, TextLine, TextPrim, TextRun, text_features,
)
from .style import EMPTY_STYLE, FONT_STYLES, Style, StyleError
from .trace import Trace
from .units import COLUMN_DOUBLE, COLUMN_SINGLE, UnitError, dpi_of, mm, pt, to_pt

__all__ = [
    "AnchorRef", "Diagram", "DiagramError", "Placement", "RenderItem",
    "flatten", "group", "note_through", "resolve", "world_point",
    "Envelope", "Trace",
    "Affine", "Rect", "Vec2", "ORIGIN", "IDENTITY", "NORTH", "SOUTH", "EAST", "WEST",
    "Prim", "RectPrim", "EllipsePrim", "PathPrim", "TextPrim", "TextLine", "TextRun",
    "ImagePrim", "Subpath", "PhantomPrim", "FILL_RULES", "text_features",
    "Style", "StyleError", "EMPTY_STYLE", "FONT_STYLES",
    "mm", "pt", "to_pt", "dpi_of", "UnitError", "COLUMN_SINGLE", "COLUMN_DOUBLE",
]
