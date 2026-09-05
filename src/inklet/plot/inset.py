"""Insets: a small panel inside a big one, and the window it magnifies.

The inset itself is easy -- put a smaller panel in a corner. What makes one
readable is the pair of things around it: a plate, so the little panel is not
sharing paper with the data it sits on, and an indicator rectangle joined to
the inset by two lines, so a reader can see *which* part of the picture got
bigger. Drawn by hand that is a rectangle in data coordinates, four corners in
millimetres, and a decision about which two of them to connect, which is where
it usually goes wrong.

    zoomed = inklet.panel(24, 16, x=(0.2, 0.4), y=(0, 1))
    ...
    parent.inset(zoomed, corner="ne", zoom=(0.2, 0.4, 0.0, 1.0))

`Panel.bracket` lives here too, because it is the same idea: something drawn in
panel millimetres from an argument given in data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError, Rect, Vec2, mm
from ..draw.annotate import bracket as draw_bracket
from ..draw.coords import active_theme, as_drawn, plot_area
from ..draw.path import polyline

__all__ = ["INDICATOR_KIND", "INSET_KIND", "inset", "panel_bracket"]

INSET_KIND = "inset"
INDICATOR_KIND = "frame"     # a muted hairline, which is what the theme calls it

_EPS = 1e-9
#: How much of a connector may lie inside either rectangle before it stops
#: being an outer tangent. A hair, not zero: a corner-to-corner segment grazes
#: the edge it starts on.
_GRAZE = 1e-6


def inset(panel, sub, *, corner: str = "ne", width: float | None = 0.35,
          pad: float | str | None = None, side: str | None = None,
          align: str = "center",
          zoom: Sequence[float] | None = None, plate: bool = True,
          connect: bool = True, **style):
    """Put `sub` inside `panel`'s plot area, on a plate, and return `panel`.

    `side="right"` (or left/top/bottom) places it outside the complete
    parent furniture. External placement is resolved at build time and follows
    later parent/child changes. `align` aligns plot areas at start/center/end. Use
    `width=None` to preserve the child's font and stroke sizes.

    `width` is the inset's share of the plot area's width, and `sub` is scaled
    to it -- **type included**, so an inset squeezed to a third of a panel has
    third-size labels and `inklet.lint` will say so. Build `sub` near its finished
    size and pass `width=None` to leave it alone, which is what a figure that
    has to survive a journal's minimum type size wants.

    `zoom=(x0, x1, y0, y1)` draws the window the inset magnifies, in the
    *parent's* data coordinates, and joins its two outer corners to the inset's
    with connector lines. Give it whenever the inset is a magnification: it is
    the difference between a second plot and a zoom.
    """
    if side is not None and side not in ("left", "right", "top", "bottom"):
        raise ValueError("inset side must be left, right, top or bottom")
    if align not in ("start", "center", "end"):
        raise ValueError("inset align must be start, center or end")
    theme = active_theme()
    gap = theme.gap("s") if pad is None else mm(pad)
    if side is not None:
        if _contains_panel(sub, panel):
            raise ValueError("external insets cannot contain their parent or form a cycle")
        if zoom is not None:
            _window(panel, zoom)  # Validate data coordinates at registration.
        panel._insets.append(ExternalInset(sub, dict(width=width, pad=gap, side=side,
            align=align, zoom=None if zoom is None else tuple(zoom), plate=plate,
            connect=connect, style=dict(style))))
        return panel._touched()
    node = sub.build() if hasattr(sub, "build") else sub
    if width is not None:
        node = _scaled_to(node, panel.width * width)
    if plate:
        node = _plated(node, theme, gap)
    node = _into_corner(node, panel.area, corner, gap)

    parts: list[Diagram] = [node]
    if zoom is not None:
        window = _window(panel, zoom)
        parts.insert(0, polyline(window.corners, closed=True,
                                 kind=INDICATOR_KIND, **style))
        if connect:
            parts[1:1] = _connectors(window, node.bbox, style)
    panel.over(*parts, clip=False)
    return panel


@dataclass(frozen=True)
class ExternalInset:
    sub: object
    options: dict


def _contains_panel(sub, parent):
    if sub is parent or (hasattr(sub, '_insets') and sub._insets is parent._insets):
        return True
    return any(_contains_panel(spec.sub, parent) for spec in getattr(sub, '_insets', ()))


def external_parts(panel, node, furniture, *, width, pad, side, align,
                   zoom, plate, connect, style):
    """Resolve one external inset in the parent's original drawing frame."""
    if width is not None:
        node = _scaled_to(node, panel.width*width)
    if plate:
        node = _plated(node, active_theme(), pad)
    box = node.bbox
    area = plot_area(node) or box
    fraction = {"start": 0., "center": .5, "end": 1.}[align]
    if side in ("left", "right"):
        dx = furniture.x0-pad-box.x1 if side == "left" else furniture.x1+pad-box.x0
        dy = panel.area.y0+fraction*panel.area.height-(area.y0+fraction*area.height)
    else:
        dx = panel.area.x0+fraction*panel.area.width-(area.x0+fraction*area.width)
        dy = furniture.y0-pad-box.y1 if side == "top" else furniture.y1+pad-box.y0
    node = node.translated(dx, dy)
    parts = []
    if zoom is not None:
        window = _window(panel, zoom)
        parts.append(polyline(window.corners, closed=True, kind=INDICATOR_KIND, **style))
        if connect:
            parts.extend(_connectors(window, plot_area(node) or node.bbox, style))
    return [as_drawn(part) for part in parts] + [node]


def _scaled_to(node: Diagram, target: float) -> Diagram:
    here = node.width
    if here <= _EPS or abs(here - target) <= _EPS:
        return node
    return node.scaled(target / here)


def _plated(node: Diagram, theme, pad: float) -> Diagram:
    """Paper under the inset, so it is not read as part of the data behind it."""
    from ..layout import frame as make_frame

    return make_frame(node, pad=pad * 0.6, kind="frame").styled(
        fill=theme.paper, stroke=theme.muted, stroke_width=theme.hairline)


def _into_corner(node: Diagram, area: Rect, corner: str, pad: float) -> Diagram:
    if corner not in ("nw", "ne", "sw", "se"):
        raise ValueError(f"corner must be nw, ne, sw or se, not {corner!r}")
    box = node.bbox
    x = (area.x0 + pad + box.width / 2.0 if corner[1] == "w"
         else area.x1 - pad - box.width / 2.0)
    y = (area.y0 + pad + box.height / 2.0 if corner[0] == "n"
         else area.y1 - pad - box.height / 2.0)
    return node.translated(x - box.center.x, y - box.center.y)


def _window(panel, zoom: Sequence[float]) -> Rect:
    """The magnified region, from data coordinates into panel millimetres."""
    try:
        x0, x1, y0, y1 = zoom
    except (TypeError, ValueError):
        raise ValueError(
            f"zoom must be (x0, x1, y0, y1) in data coordinates, not {zoom!r}"
        ) from None
    a = panel.point(x0, y0)
    b = panel.point(x1, y1)
    return Rect(min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y))


def _connectors(window: Rect, target: Rect, style: dict) -> list[Diagram]:
    """The two lines joining the window to the inset, corner to matching corner.

    The pair to draw is the one whose lines stay *outside* both rectangles --
    a connector that cuts across the window it names reads as a diagonal in the
    data. Where the two boxes overlap enough that no pair is clean, the two
    longest win, which is the same answer in every case where a clean pair
    exists and a defensible one where it does not.
    """
    pairs = list(zip(window.corners, target.corners))
    clear = [p for p in pairs
             if _inside(p, window) <= _GRAZE and _inside(p, target) <= _GRAZE]
    chosen = clear if len(clear) == 2 else sorted(
        pairs, key=lambda p: -(p[1] - p[0]).length)[:2]
    return [polyline((a, b), kind=INDICATOR_KIND, **style)
            for a, b in sorted(chosen, key=lambda p: (p[0].x, p[0].y))]


def _inside(segment: tuple[Vec2, Vec2], rect: Rect) -> float:
    """How much of a segment lies inside a box (Liang-Barsky), in millimetres."""
    a, b = segment
    dx, dy = b.x - a.x, b.y - a.y
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a.x - rect.x0), (dx, rect.x1 - a.x),
                 (-dy, a.y - rect.y0), (dy, rect.y1 - a.y)):
        if abs(p) < _EPS:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return 0.0
    return (t1 - t0) * (b - a).length


# -- brackets in data coordinates -----------------------------------------


def panel_bracket(panel, x0, x1, y=None, *, text: str | Diagram | None = None,
                  side: str = "n", tick: float | str = 1.0,
                  clear: float | str | None = None, **kwargs) -> Diagram:
    """A grouping bracket across a span of data. Backs `Panel.bracket`.

    `x0`, `x1` and `y` are data; `tick` and any padding are millimetres,
    because a tick is a mark on the page and has no meaning in the data. The
    span is horizontal for `side="n"` or `"s"` and vertical for `"e"`/`"w"`,
    where `x0`/`x1` are read as the y span and `y` as the x position.

    **`y` may be left out, and usually should be.** A significance bracket goes
    above whatever it covers, and the author does not know that number -- it is
    the tallest bar plus its error bar plus a clearance, which is arithmetic
    the panel can do and the author would have to redo every time the data
    changed. Omitted, the bracket clears everything already drawn between `x0`
    and `x1` by `clear` millimetres. A string in `y`'s place is read as the
    text, which is what makes the significance case one call:

        p.bracket("wt", "ko", "***")
    """
    if side not in ("n", "s", "e", "w"):
        raise ValueError(f"bracket side must be n, s, e or w, not {side!r}")
    across = panel.x if side in ("e", "w") else panel.y
    if text is None and _reads_as_text(across, y):
        text, y = y, None
    lo, hi = ((panel.x.map(x0), panel.x.map(x1)) if side in ("n", "s")
              else (panel.y.map(x0), panel.y.map(x1)))
    gap = active_theme().gap("xs") if clear is None else mm(clear)
    at = _over_data(panel, lo, hi, side, gap) if y is None else across.map(y)
    a, b = ((Vec2(lo, at), Vec2(hi, at)) if side in ("n", "s")
            else (Vec2(at, lo), Vec2(at, hi)))
    return draw_bracket(a, b, side=side, text=text, tick=tick, **kwargs)


def _reads_as_text(scale, value) -> bool:
    """Whether a third positional argument is the bracket's text, not its
    position.

    A string is text unless the scale it would be read on is a band scale that
    actually has a category of that name -- `p.bracket(0, 2, "ko")` on a panel
    whose *y* is categorical is a bracket at `ko`, and only the scale knows.
    """
    if not isinstance(value, (str, Diagram)):
        return False
    if isinstance(value, Diagram):
        return True
    categories = getattr(scale, "domain", ())
    return value not in tuple(categories)


def _over_data(panel, lo: float, hi: float, side: str, gap: float) -> float:
    """Where a bracket sits when it was given no position, in millimetres.

    Clear of everything drawn between the two ends of the span, which is what
    a significance bracket means: it is above *these* bars, not above the panel.
    Anything with no data of its own to clear falls back to the edge of the
    plot area.
    """
    boxes = [box for box in _drawn_boxes(panel)
             if box.x1 >= lo - _EPS and box.x0 <= hi + _EPS] \
        if side in ("n", "s") else \
        [box for box in _drawn_boxes(panel)
         if box.y1 >= lo - _EPS and box.y0 <= hi + _EPS]
    area = panel.area
    if side == "n":
        return min([area.y1] + [b.y0 for b in boxes]) - gap
    if side == "s":
        return max([area.y0] + [b.y1 for b in boxes]) + gap
    if side == "e":
        return max([area.x0] + [b.x1 for b in boxes]) + gap
    return min([area.x1] + [b.x0 for b in boxes]) - gap


def _drawn_boxes(panel) -> list[Rect]:
    """The placed box of every mark in the panel, in panel millimetres.

    Leaves rather than whole layers: one `place()` group holds every bar in a
    chart, and its box says nothing about which bar is under the bracket.

    Brackets count as things to clear. The furniture does not: an axis is
    outside the area by construction, and a bracket that cleared the title
    would climb the page one call at a time.
    """
    from ..core import group as make_group, resolve

    nodes = list(panel._under) + list(panel._content) + list(panel._brackets)
    if not nodes:
        return []
    try:
        placements = resolve(make_group(nodes))
    except DiagramError:                                 # pragma: no cover
        return [box for box in (n.envelope.bbox() for n in nodes)
                if box is not None]
    return [placed.bbox for placed in placements.values()
            if placed.diagram.prim is not None and placed.bbox is not None]
