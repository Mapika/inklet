"""Shared furniture helpers for plot regions.

The constants identify the structural nodes used by rectangular and polar
plots.  The helpers place and plate furniture without depending on either
plot implementation.
"""

from __future__ import annotations

from dataclasses import replace

from ..core import Diagram, DiagramError, Rect, Vec2
from ..draw.coords import ORIGIN_ANCHOR, plot_area

__all__ = [
    "PANEL_KIND", "AREA_KIND", "GRID_KIND", "TITLE_KIND",
    "origin_of", "plated", "into_corner", "beside",
]

PANEL_KIND = "panel"
AREA_KIND = "plot-area"
GRID_KIND = "gridline"
TITLE_KIND = "title"


def origin_of(node: Diagram) -> Vec2:
    """The point a node is lined up on: the centre of its plot area.

    A built `Panel`'s `origin` anchor already *is* that point, so reading the
    note first changes nothing for one panel. It changes everything for a
    `row`, `column` or `facets` group, whose `origin` is wherever
    `drawn_group` happened to leave (0, 0) -- the top-left corner of the first
    member, in practice. Placing a stacked pair by that is what stopped a
    column from standing in a row.
    """
    area = plot_area(node)
    if area is not None:
        return area.center
    try:
        return node.transform.apply(node.anchor_point(ORIGIN_ANCHOR))
    except DiagramError:
        box = node.envelope.bbox()
        return Vec2(0.0, 0.0) if box is None else box.center


def plated(node: Diagram, theme, pad: float) -> Diagram:
    """A key on an opaque tile, so it knocks out whatever it covers.

    Filled and *unstroked*: a legend inside the plot area has to be legible
    over gridlines and data, and a box round it is a second frame competing
    with the panel's own. What it needs is to stop the rules running under the
    type, which the fill alone does.
    """
    from ..layout import frame as make_frame

    framed=make_frame(node,pad=pad,kind="legend-plate")
    # Paint the backdrop only. Inheriting white fill/no stroke into the key
    # makes unstyled text white and turns a colorbar outline into a white tile.
    return replace(framed,children=(framed.children[0].styled(fill=theme.paper,stroke='none'),
                                   *framed.children[1:]))


def into_corner(node: Diagram, box: Rect, corner: str, pad: float) -> Diagram:
    if corner not in ("nw", "ne", "sw", "se"):
        raise ValueError(f"corner must be nw, ne, sw or se, not {corner!r}")
    here = node.bbox
    x = (box.x0 + pad + here.width / 2 if corner[1] == "w"
         else box.x1 - pad - here.width / 2)
    y = (box.y0 + pad + here.height / 2 if corner[0] == "n"
         else box.y1 - pad - here.height / 2)
    return node.translated(x - here.center.x, y - here.center.y)


def beside(node: Diagram, box: Rect, side: str, gap: float,
           center: Vec2) -> Diagram:
    """Place a key beyond existing ink, aligned with the plot's centre.

    The caller validates the side and supplies its plot-specific centre.
    """
    here = node.bbox
    if side == "right":
        at = Vec2(box.x1 + gap + here.width / 2, center.y)
    elif side == "left":
        at = Vec2(box.x0 - gap - here.width / 2, center.y)
    elif side == "top":
        at = Vec2(center.x, box.y0 - gap - here.height / 2)
    else:
        at = Vec2(center.x, box.y1 + gap + here.height / 2)
    return node.translated(at.x - here.center.x, at.y - here.center.y)
