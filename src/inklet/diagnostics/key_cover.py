"""`KEY_COVERS_DATA` -- a key set inside the plot on top of the data.

`Panel.legend(corner="sw")` puts the key on a knocked-out plate in a corner of
the plot area, and the plate is opaque by design: it is what keeps a line from
running through the words. When that corner is where the data are, the plate
erases them. Nothing collides that any other rule can see -- the key is not
text over a box, the marks are where the scales put them, nothing leaves the
panel -- and the figure lints clean with a trough of the residual, or one
whole data point, cut out of it. `ligo_gw150914` and `hubble_1929` were both
caught that way only by looking at the PNG.

So this rule asks the question directly. For every key (`legend`, `colorbar`,
`size-key`, `width-key`) that sits *inside* the plot box of the panel that
drew it, it collects the data that panel painted *before* the key -- the key
paints over those, and anything drawn after it is on top -- and measures how
much of each lies under the key's footprint:

* a marker (any shape no larger than `_MARKER_MM`, and every record of a
  marker batch) is hidden when its centre is under the key;
* a stroke -- a line, a reference line, an error bar -- by the length of it
  that runs under the key, from its flattened segments, so a sine wave's
  bounding box does not count, only the trough that actually dips in;
* a bar or another larger filled shape by its outline: the edge of a bar is
  its value, and the edge of a band is its bound. Outline lying along the plot
  box (a bar's foot on the baseline) is not counted.

A key placed by `corner="auto"` or `corner="best"` has already been kept clear
of the marks by the panel, and one set beside the plot (`side=`) is outside the
box; both are silent here by the same geometry, not by exemption. A heatmap or
an image under an inset colorbar is not judged: every corner of a matrix is
data, and the choice to inset a bar over one is a layout decision, not a slip.

**Grade: warning**, the same as `DATA_OUTSIDE`, which this is the inside-out
twin of: data the reader cannot see, with a one-word fix. The hint names the
corners that would be clear, measured the same way.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

from ..core import EllipsePrim, ImagePrim, PathPrim, Rect, Vec2
from ..draw.coords import AREA_NOTE
from ..plot.key import COLORBAR_KIND, LEGEND_KIND
from ..plot.raster import MATRIX_KIND
from .plot_rules import (_axis_readers, _data_home, _paints, _panel_name,
                         at_position)
from .rules import KEY_KINDS, Diagnostic, Item, LintContext, _mm, _shaft_segments

__all__ = ["rule_key_covers_data"]

#: `rules.KEY_KINDS` spells the size and width keys out rather than importing
#: `plot.dotplot` and `plot.network`, which the linter has no other reason to
#: load; the nouns below follow it.
_KEY_NOUNS = {LEGEND_KIND: "legend", COLORBAR_KIND: "colorbar",
              "size-key": "size key", "width-key": "width key"}

#: A shape no larger than this either way is a marker, and it is hidden when
#: its centre is. Matches `plot_rules._MARKER_MM`.
_MARKER_MM = 3.0

#: Stroke or outline under a key that counts as hidden. Less than this is a
#: line grazing the plate's edge, which `corner="auto"` itself allows (its
#: clearance is half a millimetre) and no reader would call covered.
_MIN_RUN_MM = 1.0

#: Outline within this of the plot box is the box's own edge -- a bar's foot
#: on the baseline, a band closed along the axis -- and not data.
_EDGE_MM = 0.3

#: A key is *inside* the plot when at least this much of its footprint is.
#: A `side="top"` legend dips a few tenths of a millimetre into the frame by
#: construction; it is still outside.
_INSIDE_FRACTION = 0.5

#: How much bigger than the key itself the wrapper around it may be and still
#: count as the key's footprint: the plate `_plated` puts round a legend is a
#: small padding, while the panel above it is the whole plot.
_PLATE_SLACK_MM = 3.0

_CORNERS = ("ne", "nw", "se", "sw")


def rule_key_covers_data(ctx: LintContext) -> list[Diagnostic]:
    """A key inside the plot area painted over the panel's own data."""
    order = {node_id: index for index, node_id in enumerate(ctx.nodes)}
    out: list[Diagnostic] = []
    for key_id in _keys(ctx):
        home = _panel_of(ctx, key_id)
        if home is None:
            continue
        panel_id, area = home
        unit_id = _footprint(ctx, key_id, panel_id)
        placed = ctx.placements.get(unit_id)
        cover = None if placed is None else placed.bbox
        if cover is None or not _inside(cover, area):
            continue
        data = _data_under(ctx, panel_id, unit_id, order)
        hidden = _hidden(ctx, data, cover, area)
        if not hidden:
            continue
        out.append(_finding(ctx, key_id, unit_id, panel_id, area, cover,
                            data, hidden))
    return out


# -- finding the keys and what they sit on ----------------------------------


def _keys(ctx: LintContext) -> list[str]:
    """Every key node, outermost only: a legend inside a size key's title
    stack is one key, not two."""
    found = []
    for node_id, node in ctx.nodes.items():
        if node.kind not in KEY_KINDS:
            continue
        if any(getattr(ctx.nodes.get(step), "kind", None) in KEY_KINDS
               for step in ctx.ancestors(node_id)):
            continue
        found.append(node_id)
    return sorted(found)


def _panel_of(ctx: LintContext, node_id: str) -> tuple[str, Rect] | None:
    """The nearest enclosing plot panel with its plot box in world space."""
    for step in ctx.ancestors(node_id):
        node = ctx.nodes.get(step)
        if node is None or node.kind != "panel":
            continue
        notes = getattr(node, "notes", None)
        area = notes.get(AREA_NOTE) if isinstance(notes, Mapping) else None
        placed = ctx.placements.get(step)
        if not isinstance(area, Rect) or placed is None:
            return None
        return step, area.transform(placed.world)
    return None


def _footprint(ctx: LintContext, key_id: str, panel_id: str) -> str:
    """The outermost node that is still just this key: the key, its plate and
    the wrappers that placed them, stopping short of anything that also holds
    other ink (the panel, a layer of several keys)."""
    placed = ctx.placements.get(key_id)
    own = None if placed is None else placed.bbox
    best = key_id
    for step in ctx.ancestors(key_id):
        if step == panel_id:
            break
        placed = ctx.placements.get(step)
        box = None if placed is None else placed.bbox
        if box is None or own is None:
            break
        if not _within(box, own.pad(_PLATE_SLACK_MM)):
            break
        best = step
    return best


def _inside(cover: Rect, area: Rect) -> bool:
    overlap = cover.overlap(area)
    size = cover.width * cover.height
    if overlap is None or size <= 0.0:
        return False
    return overlap.width * overlap.height >= _INSIDE_FRACTION * size


def _within(outer: Rect, inner: Rect) -> bool:
    return (outer.x0 >= inner.x0 - 1e-9 and outer.y0 >= inner.y0 - 1e-9
            and outer.x1 <= inner.x1 + 1e-9 and outer.y1 <= inner.y1 + 1e-9)


def _data_under(ctx: LintContext, panel_id: str, unit_id: str,
                order: Mapping[str, int]) -> list[Item]:
    """The panel's data items painted before the key, which it paints over."""
    start = order.get(unit_id, 0)
    out = []
    for item in ctx.items:
        if item.is_text or not item.draws or order.get(item.id, 0) >= start:
            continue
        if isinstance(item.prim, ImagePrim):
            continue
        chain = ctx.chain(item.id)
        if panel_id not in chain or unit_id in chain:
            continue
        if any(_matrix(ctx.nodes.get(step)) for step in chain):
            continue
        home = _data_home(ctx, item.id)
        if home is None or home[0] != panel_id or not _paints(item):
            continue
        out.append(item)
    return out


def _matrix(node) -> bool:
    if node is None:
        return False
    if node.kind == MATRIX_KIND:
        return True
    notes = getattr(node, "notes", None)
    return isinstance(notes, Mapping) and "matrix_sampling" in notes


# -- measuring what is under a rectangle --------------------------------------


class _Hidden:
    """What one item loses under one rectangle."""

    __slots__ = ("item", "markers", "of", "length", "kind", "points")

    def __init__(self, item: Item, kind: str, *, markers: int = 0, of: int = 0,
                 length: float = 0.0, points: tuple[Vec2, ...] = ()) -> None:
        self.item, self.kind = item, kind
        self.markers, self.of, self.length = markers, of, length
        self.points = points


def _hidden(ctx: LintContext, data: list[Item], cover: Rect,
            area: Rect) -> list[_Hidden]:
    out = []
    for item in data:
        found = _hidden_one(ctx, item, cover, area)
        if found is not None:
            out.append(found)
    return out


def _hidden_one(ctx: LintContext, item: Item, cover: Rect,
                area: Rect) -> _Hidden | None:
    from ..core import MarkerBatchPrim
    prim = item.prim
    if not _touches(item.bbox, cover):
        return None
    if isinstance(prim, MarkerBatchPrim):
        centres = [item.world.apply(Vec2(x, y)) for x, y, _, _, _ in prim.records()]
        under = tuple(c for c in centres if _holds(cover, c))
        if not under:
            return None
        return _Hidden(item, "marker", markers=len(under), of=len(centres),
                       points=under)
    box = item.bbox
    stroked = isinstance(prim, PathPrim) and not prim.filled
    if not stroked and max(box.width, box.height) <= _MARKER_MM:
        centre = box.center
        if not _holds(cover, centre):
            return None
        return _Hidden(item, "marker", markers=1, of=1, points=(centre,))
    if stroked:
        run = sum(_length_in(a, b, cover) for a, b in _shaft_segments(ctx, item))
        return _Hidden(item, "line", length=run) if run >= _MIN_RUN_MM else None
    run = sum(_length_in(a, b, cover) for a, b in _outline(ctx, item, area))
    return _Hidden(item, "edge", length=run) if run >= _MIN_RUN_MM else None


def _touches(a: Rect, b: Rect) -> bool:
    """Boxes that share any point -- `Rect.overlap` says None for a vertical
    stroke's zero-width box, which is exactly the stroke to measure."""
    return a.x0 <= b.x1 and b.x0 <= a.x1 and a.y0 <= b.y1 and b.y0 <= a.y1


def _holds(box: Rect, point: Vec2) -> bool:
    return box.x0 <= point.x <= box.x1 and box.y0 <= point.y <= box.y1


def _outline(ctx: LintContext, item: Item, area: Rect):
    """A filled shape's edges in world space, minus those on the plot box."""
    prim = item.prim
    if isinstance(prim, PathPrim):
        edges = list(_shaft_segments(ctx, item))
        # A filled path is closed by its fill whether or not its subpaths
        # say so, and `_shaft_segments` only closes the ones that do.
        for sub in prim.subpaths:
            if len(sub.points) >= 3 and not sub.closed:
                a = item.world.apply(sub.points[-1])
                b = item.world.apply(sub.points[0])
                edges.append((a, b))
    elif isinstance(prim, EllipsePrim):
        ring = [item.world.apply(Vec2(prim.rx * math.cos(t), prim.ry * math.sin(t)))
                for t in (2.0 * math.pi * k / 48 for k in range(48))]
        edges = list(zip(ring, ring[1:] + ring[:1]))
    else:
        corners = list(item.bbox.corners)
        edges = list(zip(corners, corners[1:] + corners[:1]))
    return [(a, b) for a, b in edges if not _on_edge(a, b, area)]


def _on_edge(a: Vec2, b: Vec2, area: Rect) -> bool:
    for fixed, lo, hi in ((lambda p: p.x, area.x0, area.x1),
                          (lambda p: p.y, area.y0, area.y1)):
        for side in (lo, hi):
            if abs(fixed(a) - side) <= _EDGE_MM and abs(fixed(b) - side) <= _EDGE_MM:
                return True
    return False


def _length_in(a: Vec2, b: Vec2, box: Rect) -> float:
    """Length of segment ab inside an axis-aligned box (Liang-Barsky)."""
    dx, dy = b.x - a.x, b.y - a.y
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a.x - box.x0), (dx, box.x1 - a.x),
                 (-dy, a.y - box.y0), (dy, box.y1 - a.y)):
        if p == 0.0:
            if q < 0.0:
                return 0.0
            continue
        t = q / p
        if p < 0.0:
            if t > t1:
                return 0.0
            t0 = max(t0, t)
        else:
            if t < t0:
                return 0.0
            t1 = min(t1, t)
    return max(0.0, t1 - t0) * math.hypot(dx, dy)


# -- the sentence ---------------------------------------------------------------


def _finding(ctx: LintContext, key_id: str, unit_id: str, panel_id: str,
             area: Rect, cover: Rect, data: list[Item],
             hidden: list[_Hidden]) -> Diagnostic:
    noun = _KEY_NOUNS.get(ctx.nodes[key_id].kind, "key")
    named = _panel_name(ctx, panel_id)
    plated = _plated(ctx, unit_id, cover)
    verb = "hides" if plated else "is drawn over"
    readers = _axis_readers(ctx, panel_id, area)
    parts = _parts(ctx, hidden, readers)
    where = _corner_of(cover, area)
    message = (f"the {noun} {('in the ' + where + ' corner ') if where else ''}"
               f"of {named} {verb} data: {'; '.join(parts)}")
    clear = _clear_corners(ctx, cover, area, data, where)
    if len(clear) == 1:
        first = f"move it to corner={clear[0]!r}, which is clear of the data"
    elif clear:
        spelled = ", ".join(repr(c) for c in clear[:-1]) + f" or {clear[-1]!r}"
        first = f"move it to corner={spelled}, which are clear of the data"
    else:
        first = "no other corner is clear at this size, so"
    if where is None:
        room = "widen the axis range to make room for it"
    else:
        room = (f"extend the y range {'upward' if where[0] == 'n' else 'downward'}"
                f" to make room for it")
    joiner = "; or" if clear else ""
    hint = (f"{first}{joiner} pass corner='auto' to search the plot for clear "
            f"space, side='right' (or another side) to set it outside the plot, "
            f"or {room}")
    targets = {unit_id}
    targets.update(h.item.id for h in hidden)
    return Diagnostic(
        code="KEY_COVERS_DATA",
        severity="warning",
        message=message,
        targets=tuple(sorted(targets)),
        where=cover,
        hint=hint,
    )


def _plated(ctx: LintContext, unit_id: str, cover: Rect) -> bool:
    """Whether the key stands on an opaque plate covering its footprint."""
    size = cover.width * cover.height
    for item in ctx.items:
        if unit_id not in ctx.chain(item.id) or not item.is_backdrop:
            continue
        if item.bbox.width * item.bbox.height >= 0.8 * size:
            return True
    return False


def _parts(ctx: LintContext, hidden: list[_Hidden], readers) -> list[str]:
    markers = [h for h in hidden if h.kind == "marker"]
    strokes = [h for h in hidden if h.kind != "marker"]
    parts = []
    if markers:
        count = sum(h.markers for h in markers)
        points = [p for h in markers for p in h.points]
        spelled = [at_position(p, readers) for p in points[:3]]
        spelled = [s for s in spelled if s]
        more = "" if len(points) <= 3 else f" and {len(points) - 3} more"
        where = f" ({', '.join(spelled)}{more})" if spelled else ""
        parts.append(f"{count} marker{'s' if count != 1 else ''}{where}")
    for h in sorted(strokes, key=lambda h: (-h.length, h.item.id))[:4]:
        what = "of line" if h.kind == "line" else "of the outline of"
        parts.append(f"{_mm(h.length)} {what} {_series(ctx, h.item)}")
    if len(strokes) > 4:
        parts.append(f"and {len(strokes) - 4} more strokes")
    return parts


def _series(ctx: LintContext, item: Item) -> str:
    """The series name the panel remembered for this stroke, else its id."""
    for step in reversed(ctx.chain(item.id)):
        node = ctx.nodes.get(step)
        notes = getattr(node, "notes", None)
        if isinstance(notes, Mapping) and notes.get("series_line"):
            return f"{notes['series_line']!r} ({item.id})"
        if node is not None and node.kind == "panel":
            break
    return f"{item.node.kind or 'stroke'} ({item.id})"


def _corner_of(cover: Rect, area: Rect) -> str | None:
    """Which corner of the plot the key sits in, or None when it is not in one."""
    third_x, third_y = area.width / 3.0, area.height / 3.0
    c = cover.center
    ns = "n" if c.y < area.y0 + third_y else "s" if c.y > area.y1 - third_y else ""
    ew = "w" if c.x < area.x0 + third_x else "e" if c.x > area.x1 - third_x else ""
    return ns + ew if ns and ew else None


def _clear_corners(ctx: LintContext, cover: Rect, area: Rect,
                   data: list[Item], current: str | None) -> list[str]:
    """The other corners the same key would cover nothing in, at the same
    inset from the plot box as it has now."""
    inset_x = max(0.0, min(cover.x0 - area.x0, area.x1 - cover.x1))
    inset_y = max(0.0, min(cover.y0 - area.y0, area.y1 - cover.y1))
    w, h = cover.width, cover.height
    clear = []
    for corner in _CORNERS:
        if corner == current:
            continue
        x0 = area.x0 + inset_x if corner[1] == "w" else area.x1 - inset_x - w
        y0 = area.y0 + inset_y if corner[0] == "n" else area.y1 - inset_y - h
        box = Rect(x0, y0, x0 + w, y0 + h)
        if not any(_hidden_one(ctx, item, box, area) for item in data):
            clear.append(corner)
    return clear
