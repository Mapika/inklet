"""Direct labels for named curves: the series name at the line, not in a key.

`Panel.label_lines` writes each named line, step or ECDF's name next to the
curve itself, in the curve's colour, which is what a journal figure with more
than two or three curves wants instead of a legend the reader has to match by
colour.

Two placements:

* ``where="end"`` (the default) sets the names in a column just past the
  right-most curve end, each at the height its curve ends at. Names that
  would collide are pushed apart by the least total movement that keeps them
  in order and a theme gap apart (`layout.label_search.stack`), and a name
  moved off its curve's end gets a hairline leader back to it. The column
  sits outside the plot area, beside the data, like a key on the right.
* ``where="inside"`` puts each name inside the plot area along the last part
  of its own curve -- just above or below it, preferring positions near the
  end -- chosen jointly by the label search in `layout.label_search`, so no
  name sits on another name, is crossed by a curve, or sits closer to a
  different curve than its own.

A curve is found by the name it was drawn under (`name=` on `line`, `step`
or `ecdf`). Placement waits for `Panel.build`, like `label_points`, so it
sees every mark. A name that could not be placed without a collision is still
drawn and is listed in the node's `line_labels` note under `unresolved`, which
`inklet.lint` reports as `LABEL_UNPLACED`.
"""
from __future__ import annotations

import math
from typing import Sequence

from ..core import Diagram, DiagramError, PathPrim, Rect, Vec2, mm, resolve
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..layout.label_search import (Candidate, ObstacleField, Weights, seed_of,
                                   solve, stack)
from ..themes.color import readable
from .axis import text_node

__all__ = ["LINE_LABEL_KIND", "LINE_LEADER_KIND", "LINE_LABELS_KIND",
           "SERIES_NOTE", "label_lines", "tag_series"]

#: Kind of each name.
LINE_LABEL_KIND = "line-label"
#: Kind of each leader from a curve end to its name.
LINE_LEADER_KIND = "label-leader"
#: Kind of the group holding one call's names and leaders.
LINE_LABELS_KIND = "line-labels"
#: Note on a drawn curve naming its series, for `label_lines` to find.
SERIES_NOTE = "series_line"

#: A name moved further than this fraction of its type size off its curve's
#: end gets a leader.
_SHIFT_OF_TYPE = 0.25
#: Room left for leaders between the curve ends and the column, in theme
#: `xs` gaps, when any name needs one.
_LEADER_ROOM = 2.5
#: Positions sampled along each curve for `where="inside"`.
_SAMPLES = 24
#: Cost of sitting at the start of the curve rather than its end.
_END_PREFERENCE = 6.0
#: Cost of a name nearer another curve than its own.
_AMBIGUOUS = 12.0


def tag_series(node: Diagram, name: str | None) -> Diagram:
    """Mark a drawn curve as the series `name` (no-op without a name)."""
    if name is not None:
        node.note(SERIES_NOTE, str(name))
    return node


def curves(marks: Sequence[Diagram]) -> dict[str, list[Vec2]]:
    """Each named curve's vertices in page coordinates, in drawing order.

    A name drawn twice keeps its last curve.
    """
    found: dict[str, list[Vec2]] = {}
    for art in marks:
        for placed in resolve(art).values():
            node = placed.diagram
            name = node.notes.get(SERIES_NOTE)
            if name is None or not isinstance(node.prim, PathPrim):
                continue
            pts: list[Vec2] = []
            for sub in node.prim.subpaths:
                pts.extend(placed.world.apply(v) for v in sub.points)
            if pts:
                found.pop(name, None)
                found[name] = pts
    return found


def defer(panel, name: str | Sequence[str] | None, **kwargs):
    """`Panel.label_lines`: hold the call's place until the panel is built."""
    from .point_labels import PENDING_KIND
    from .series import series_names

    names = series_names(name)
    if names is not None:
        names = [str(n) for n in names]
    theme = active_theme()

    def place(marks):
        import inklet
        token = inklet._theme_context.set(theme)
        try:
            return label_lines(panel, names, marks=marks, **kwargs)
        finally:
            inklet._theme_context.reset(token)

    holder = Diagram(kind=PENDING_KIND)
    panel._deferred[id(holder)] = place
    panel._over.append(holder)
    return panel._touched()


def _inside(p: Vec2, area: Rect, eps: float = 1e-6) -> bool:
    return (area.x0 - eps <= p.x <= area.x1 + eps
            and area.y0 - eps <= p.y <= area.y1 + eps)


def _visible(pts: Sequence[Vec2], area: Rect) -> list[Vec2]:
    """The curve's vertices from its first to its last inside the area."""
    inside = [k for k, p in enumerate(pts) if _inside(p, area)]
    if not inside:
        return []
    return [p for p in pts[inside[0]:inside[-1] + 1] if _inside(p, area)]


def _box(node: Diagram, x0: float, cy: float) -> Rect:
    b = node.bbox
    return Rect(x0, cy - b.height / 2, x0 + b.width, cy + b.height / 2)


def _distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    length = dx * dx + dy * dy
    t = 0.0 if length == 0 else max(0.0, min(1.0, ((p.x - a.x) * dx
                                                   + (p.y - a.y) * dy) / length))
    return math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy)


def _nearest(p: Vec2, pts: Sequence[Vec2]) -> float:
    if len(pts) == 1:
        return math.hypot(p.x - pts[0].x, p.y - pts[0].y)
    return min(_distance(p, a, b) for a, b in zip(pts, pts[1:]))


def label_lines(panel, name: str | Sequence[str] | None = None, *,
                where: str = "end", size: float | str | None = None,
                gap: float | str | None = None, leader: bool = True,
                color: bool = True, markup: bool = True,
                leader_style: dict | None = None,
                marks: Sequence[Diagram] | None = None, **style) -> Diagram:
    """Name each curve at the curve. See `Panel.label_lines`."""
    from .point_labels import _obstacles

    if where not in ("end", "inside"):
        raise ValueError('label_lines where= is "end" or "inside"')
    theme = active_theme()
    if "fill" in style:
        style["text_fill"] = style.pop("fill")
    font = theme.font_size_small if size is None else mm(size)
    clear = theme.gap("xs") if gap is None else mm(gap)
    spacing = theme.gap("xs")
    if marks is None:
        marks = [*panel._content, *panel._over]
    found = curves(marks)
    names = [name] if isinstance(name, str) else name
    if names is None:
        names = list(found)
        if not names:
            raise DiagramError(
                "label_lines() found no named curves: pass name= to line(), "
                "step() or ecdf()")
    else:
        missing = [n for n in names if n not in found]
        if missing:
            raise DiagramError(
                f"label_lines() has no curve named {missing[0]!r}; named "
                f"curves are {sorted(found)!r}")
    area = panel.area
    paths = {n: _visible(found[n], area) for n in names}
    hidden = [n for n in names if not paths[n]]
    shown = [n for n in names if paths[n]]
    colours = {k.name: k.color for k in panel.keys}
    nodes = {}
    for n in shown:
        own = dict(style)
        if color and "text_fill" not in own and colours.get(n):
            # The series' own hue, darkened only as far as text needs to
            # read on the paper (a yellow line keeps a legible ochre name).
            own["text_fill"] = readable(colours[n], theme.paper)
        nodes[n] = text_node(n, font, LINE_LABEL_KIND, align="left",
                             markup=markup, **own)
    boxes, segments, polygons, flags = _obstacles(list(marks), split=True)
    field = ObstacleField(cell=max(2 * font, 1.0))
    for b, flag in zip(boxes, flags):
        field.add_box((b.x0, b.y0, b.x1, b.y1), mark=flag)
    for a, b in segments:
        field.add_segment((a.x, a.y, b.x, b.y))
    for poly in polygons:
        field.add_area(poly)
    weights = Weights()
    if where == "end":
        placed, leaders, unresolved = _at_ends(
            shown, paths, nodes, field, weights, area, font, clear, spacing,
            leader)
    else:
        placed, unresolved = _along(shown, paths, nodes, field, weights, area,
                                    font, clear, spacing)
        leaders = {}
    ink = style.get("text_fill", theme.ink)
    parts: list = []
    for n in shown:
        if n in leaders:
            a, b = leaders[n]
            line_style = {"stroke": colours.get(n) or ink if color else ink,
                          "stroke_width": theme.hairline}
            line_style.update(leader_style or {})
            parts.append(polyline((a, b), kind=LINE_LEADER_KIND, **line_style))
    for n in shown:
        parts.append((placed[n].center, nodes[n]))
    node = (draw_place(parts, origin=(0, 0), kind=LINE_LABELS_KIND) if parts
            else Diagram(kind=LINE_LABELS_KIND))
    node.notes["line_labels"] = {
        "count": len(names),
        "where": where,
        "leaders": [n for n in shown if n in leaders],
        "unresolved": sorted(set(unresolved) | set(hidden),
                             key=list(names).index),
    }
    return node


def _at_ends(names, paths, nodes, field, weights, area, font, clear, spacing,
             leader):
    """The column past the curve ends; see the module docstring."""
    ends = {n: paths[n][-1] for n in names}
    if not names:
        return {}, {}, []
    heights = [nodes[n].bbox.height for n in names]
    centres = stack([ends[n].y for n in names], heights, gap=spacing,
                    top=area.y0, bottom=area.y1)
    at = dict(zip(names, centres))
    shifted = {n for n in names
               if abs(at[n] - ends[n].y) > _SHIFT_OF_TYPE * font}
    x0 = max(e.x for e in ends.values()) + clear
    if shifted and leader:
        x0 += _LEADER_ROOM * clear
    placed = {n: _box(nodes[n], x0, at[n]) for n in names}
    leaders = {}
    for n in names:
        e = ends[n]
        # A name level with its end but set back from it (another curve ends
        # further right) is joined to it too.
        if leader and (n in shifted or x0 - e.x > 2 * clear + 1e-9):
            leaders[n] = (Vec2(e.x + clear / 2, e.y),
                          Vec2(x0 - clear / 3, at[n]))
    unresolved = []
    for n in names:
        b = placed[n]
        _, conflicts, _ = field.cost((b.x0, b.y0, b.x1, b.y1),
                                     spacing=spacing, weights=weights)
        if conflicts:
            unresolved.append(n)
    return placed, leaders, unresolved


def _along(names, paths, nodes, field, weights, area, font, clear, spacing):
    """Beside each curve's last stretch, chosen jointly; see module docs."""
    from .point_labels import _within

    options: list[list[Candidate]] = []
    for n in names:
        pts = paths[n]
        node = nodes[n]
        w, h = node.bbox.width, node.bbox.height
        lengths = [0.0]
        for a, b in zip(pts, pts[1:]):
            lengths.append(lengths[-1] + math.hypot(b.x - a.x, b.y - a.y))
        total = lengths[-1]
        samples: list[tuple[float, Vec2]] = []
        for k in range(_SAMPLES + 1):
            t = 1.0 - k / _SAMPLES
            s = t * total
            j = 0
            while j < len(lengths) - 2 and lengths[j + 1] < s:
                j += 1
            a, b = pts[j], pts[min(j + 1, len(pts) - 1)]
            seg = lengths[min(j + 1, len(lengths) - 1)] - lengths[j]
            u = 0.0 if seg <= 0 else (s - lengths[j]) / seg
            samples.append((t, Vec2(a.x + (b.x - a.x) * u,
                                    a.y + (b.y - a.y) * u)))
        others = [paths[m] for m in names if m != n]
        found: list[tuple[float, int, Candidate]] = []
        rank = 0
        end = pts[-1]
        spots = [(1.0, Rect(end.x + clear, end.y - h / 2,
                            end.x + clear + w, end.y + h / 2))]
        for t, p in samples:
            for x0 in (p.x - w, p.x - w / 2, p.x):
                spots.append((t, Rect(x0, p.y - clear / 2 - h, x0 + w,
                                      p.y - clear / 2)))
                spots.append((t, Rect(x0, p.y + clear / 2, x0 + w,
                                      p.y + clear / 2 + h)))
        for t, box in spots:
            rank += 1
            if not _within(box, area):
                continue
            b = (box.x0, box.y0, box.x1, box.y1)
            cost, conflicts, covered = field.cost(b, spacing=spacing,
                                                  weights=weights)
            cost += _END_PREFERENCE * (1.0 - t)
            mine = _nearest(box.center, pts)
            if any(_nearest(box.center, o) < mine for o in others):
                cost += _AMBIGUOUS
            found.append((cost, rank, Candidate(b, None, cost, conflicts,
                                                box, covered)))
        if not found:
            # Nowhere inside: fall back on the end, reported as unresolved.
            box = Rect(end.x - w, end.y - clear / 2 - h, end.x,
                       end.y - clear / 2)
            found.append((0.0, 0, Candidate((box.x0, box.y0, box.x1, box.y1),
                                            None, 0.0, 1, box, 0)))
        found.sort(key=lambda item: (item[0], item[1]))
        options.append([c for _, _, c in found[:64]])
    solution = solve(options, spacing=spacing, weights=weights,
                     seed=seed_of(tuple(names),
                                  tuple((round(paths[n][-1].x, 4),
                                         round(paths[n][-1].y, 4))
                                        for n in names)))
    placed = {n: options[i][c].data for i, (n, c)
              in enumerate(zip(names, solution.chosen))}
    unresolved = [names[i] for i in solution.conflicted]
    return placed, unresolved
