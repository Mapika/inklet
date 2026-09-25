"""The compiled scene viewer; moved to `inklet.render._viewer` in 4.3.

Deprecated: importing this path warns from Inklet 4.4 and the path is removed
in 5.0. Use RenderScene.to_html() instead.
"""
from inklet._compat import moved_module as _moved_module
from inklet.render._viewer import (  # noqa: F401
    EllipsePrim,
    PathPrim,
    RectPrim,
    _marker_geometry,
    _render_svg,
    _simple_polygon,
    parse_color,
    to_html,
)

_moved_module(__name__, 'inklet.render._viewer',
              hint='use RenderScene.to_html() instead')
