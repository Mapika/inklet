"""The compiled scene viewer; moved to `inklet.render._viewer` in 4.3.

This path keeps working and re-exports the same objects. New code should
import from `inklet.render._viewer`.
"""
from inklet.render._viewer import (  # noqa: F401
    EllipsePrim,
    Path,
    PathPrim,
    RectPrim,
    _marker_geometry,
    _render_svg,
    _simple_polygon,
    base64,
    html,
    json,
    math,
    parse_color,
    re,
    to_html,
)
