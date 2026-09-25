"""Gantt charts and event timelines: things placed in time.

`gantt` draws one bar per task from its start to its end, on the row its
label names (a band y scale), against a time or numeric x scale. A task
whose start equals its end is a milestone, drawn as a diamond. Tasks can be
coloured by group, with one legend entry per group.

`timeline` draws events as stems off a base line, each labelled at the end
of its stem. Stems alternate above and below the line and step outward
only as far as needed to keep neighbouring labels from overlapping, which
is what makes a dense run of events legible.

Times are whatever the x scale takes: numbers on a linear scale, or dates,
datetimes and ISO strings on `inklet.dates` (a panel built with
`x=("2024-01-01", "2024-12-31")` has one).
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Rect, Vec2, mm
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND, marker as make_marker
from . import marks as _marks
from .label_spread import label_text, on_fill

__all__ = ["gantt", "timeline"]

#: A milestone diamond, as a fraction of the row's bar thickness.
_MILESTONE_OF_BAR = 1.25


def gantt(panel, tasks: Sequence[Sequence], *, groups: Sequence | None = None,
          color=None, width: float = 0.6, labels: bool = False,
          **style) -> tuple[Diagram, dict]:
    """Draw a Gantt chart on `panel`. See `Panel.gantt`.

    Returns `(node, colour by group)`.
    """
    rows = [tuple(t) for t in tasks]
    if not rows:
        raise DiagramError("gantt() was given no tasks")
    if any(len(t) not in (3, 4) for t in rows):
        raise DiagramError("each gantt task is (row, start, end) or (row, start, end, text)")
    theme = active_theme()
    palette: dict = {}
    if groups is not None:
        groups = list(groups)
        if len(groups) != len(rows):
            raise DiagramError(f"gantt groups= has {len(groups)} labels for {len(rows)} tasks")
        order = list(dict.fromkeys(groups))
        if isinstance(color, Mapping):
            palette = {g: color[g] for g in order}
        elif color is None or isinstance(color, str):
            palette = {g: theme.color(i + 1) for i, g in enumerate(order)}
        else:
            given = list(color)
            palette = {g: given[i % len(given)] for i, g in enumerate(order)}
        fills = [palette[g] for g in groups]
    elif color is None or isinstance(color, str):
        fills = [color or theme.color(5)] * len(rows)
    else:
        fills = list(color)
        if len(fills) != len(rows):
            raise DiagramError("gantt color= is one colour or one per task")
    stroke = style.pop("stroke", None)
    stroke_width = style.pop("stroke_width", None)
    bars, marks, written = [], [], []
    for (row, start, end, *text), fill in zip(rows, fills):
        lo, hi = _marks._slot(panel.y, row, width)
        a, b = panel.x.map(start), panel.x.map(end)
        if b < a - 1e-9:
            raise DiagramError(f"gantt task on {row!r} ends before it starts")
        mid = (lo + hi) / 2
        if abs(b - a) < 1e-9:
            size = (hi - lo) * _MILESTONE_OF_BAR
            marks.append((Vec2(a, mid), make_marker("diamond", size, fill=fill,
                                                    stroke=theme.paper,
                                                    stroke_width=theme.hairline)))
            continue
        bars.append(_marks._rect(Vec2((a + b) / 2, mid), b - a, hi - lo, fill,
                                 stroke, stroke_width))
        if labels and text:
            node = label_text(text[0], text_fill=on_fill(fill))
            if node.bbox.width + theme.gap("xs") * 2 <= b - a:
                written.append(draw_place([(Vec2(a + theme.gap("xs"), mid), node)],
                                          anchor="w", origin=(0, 0)))
            else:
                written.append(draw_place([(Vec2(b + theme.gap("xs"), mid),
                                            label_text(text[0]))], anchor="w", origin=(0, 0)))
    node = draw_place(bars + marks + written, **style)
    node.notes["gantt"] = {"tasks": len(rows)}
    return node, palette


def timeline(panel, events: Sequence[Sequence], *, at: float | None = None,
             color: str | None = None, size: float | str | None = None,
             levels: Sequence[int] | None = None, line: bool = True,
             **style) -> tuple[Diagram, list[int]]:
    """Draw an event timeline on `panel`. See `Panel.timeline`.

    Returns `(node, level per event)`: +1, +2, ... above the line and
    -1, -2, ... below it.
    """
    items = [tuple(e) for e in events]
    if not items:
        raise DiagramError("timeline() was given no events")
    if any(len(e) != 2 for e in items):
        raise DiagramError("each timeline event is (when, label)")
    theme = active_theme()
    ink = color or theme.ink
    dot = theme.font_size * 0.5 if size is None else mm(size)
    area = panel.area
    base = area.center.y if at is None else panel.y.map(at)
    xs = [panel.x.map(when) for when, _ in items]
    nodes = [label_text(text) for _, text in items]
    gap = theme.gap("xs")
    pitch = max(n.bbox.height for n in nodes) + gap * 1.5
    first = pitch * 0.9
    chosen = list(levels) if levels is not None else _levels(xs, nodes, gap)
    if len(chosen) != len(items):
        raise DiagramError(f"timeline levels= has {len(chosen)} entries for {len(items)} events")
    if any(level == 0 for level in chosen):
        raise DiagramError("timeline levels are +1, +2, ... above or -1, -2, ... below; not 0")
    stems, dots, written = [], [], []
    stem = {"stroke": ink, "stroke_width": theme.hairline, "stroke_linecap": "butt"}
    for x, node, level in zip(xs, nodes, chosen):
        sign = -1.0 if level > 0 else 1.0
        reach = first + pitch * (abs(level) - 1)
        tip = base + sign * reach
        stems.append(polyline((Vec2(x, base), Vec2(x, tip)), kind=MARK_LINE_KIND, **stem))
        dots.append((Vec2(x, base), make_marker("circle", dot, fill=ink,
                                                  stroke=theme.paper,
                                                  stroke_width=theme.hairline)))
        written.append(draw_place([(Vec2(x - gap * 0.2, tip), node)],
                                  anchor="sw" if level > 0 else "nw", origin=(0, 0)))
    rules = []
    if line:
        rules.append(polyline((Vec2(area.x0, base), Vec2(area.x1, base)),
                              kind=MARK_LINE_KIND, stroke=theme.ink,
                              stroke_width=theme.stroke, stroke_linecap="butt"))
    node = draw_place(rules + stems + dots + written, **style)
    node.notes["timeline"] = {"levels": tuple(chosen)}
    return node, chosen


def _levels(xs: Sequence[float], nodes: Sequence[Diagram], gap: float) -> list[int]:
    """Alternate sides; on each side take the lowest level whose label does
    not overlap a label already there. Labels are written east from the
    stem, so a label occupies `[x, x + width + gap]`."""
    order = sorted(range(len(xs)), key=lambda i: (xs[i], i))
    taken: dict[int, list[tuple[float, float]]] = {}
    out = [0] * len(xs)
    side = 1
    for i in order:
        span = (xs[i], xs[i] + nodes[i].bbox.width + gap)
        best, clear = None, None
        for sign in (side, -side):
            level = sign
            while any(a < span[1] and span[0] < b for a, b in taken.get(level, [])):
                level += sign
            if best is None or abs(level) < abs(best):
                best = level
            # A stem longer than one level passes the labels nearer the line;
            # prefer a side where it cuts through none of them.
            crossed = any(a < xs[i] < b for step in range(sign, level, sign)
                          for a, b in taken.get(step, []))
            if not crossed and (clear is None or abs(level) < abs(clear)):
                clear = level
        if clear is not None:
            best = clear
        taken.setdefault(best, []).append(span)
        out[i] = best
        side = -1 if best > 0 else 1
    return out
