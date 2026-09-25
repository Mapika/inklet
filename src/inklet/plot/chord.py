"""Chord and arc diagrams: flows between groups around a ring or along a line.

`chord_layout` does the angles and draws nothing. `Panel.chord` draws the
ring segments and ribbons into the plot area; `Panel.arc_diagram` puts nodes
on a line and joins them with arcs whose widths are the edge weights.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, EllipsePrim, RectPrim, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import encoded, path, straight_cubic
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND, arc_cubics
from ..themes.color import mix
from .axis import text_node

__all__ = ["ChordGroup", "ChordRibbon", "ChordLayout", "chord_layout", "chord",
           "arc_diagram"]

LABEL_KIND = "label"


@dataclass(frozen=True)
class ChordGroup:
    """One group's arc on the ring: `start` and `end` in degrees clockwise
    from `start` of the layout, and its `value` (row sum, or row plus column
    sum when directed)."""
    name: str
    start: float
    end: float
    value: float


@dataclass(frozen=True)
class ChordRibbon:
    """A flow between `source` and `target` (group indices): the angles of
    its two ends and the values they stand for."""
    source: int
    target: int
    source_span: tuple[float, float]
    target_span: tuple[float, float]
    value: float
    back: float


@dataclass(frozen=True)
class ChordLayout:
    groups: tuple[ChordGroup, ...]
    ribbons: tuple[ChordRibbon, ...]
    total: float


def _matrix(matrix) -> list[list[float]]:
    rows = [list(r.tolist() if hasattr(r, "tolist") else r)
            for r in (matrix.tolist() if hasattr(matrix, "tolist") else matrix)]
    n = len(rows)
    if n == 0 or any(len(r) != n for r in rows):
        raise DiagramError("a chord diagram needs a square matrix")
    out = []
    for r in rows:
        line = []
        for v in r:
            if v is None:
                v = 0.0
            if isinstance(v, bool) or not isinstance(v, Real) or v < 0 or not math.isfinite(v):
                raise DiagramError(f"chord matrix values must be finite and zero or more, got {v!r}")
            line.append(float(v))
        out.append(line)
    return out


def chord_layout(matrix, names: Sequence[str] | None = None, *, gap: float = 2.0,
                 start: float = -90.0, directed: bool = False,
                 sort: bool = False) -> ChordLayout:
    """Angles of the groups and ribbons of a chord diagram, without drawing.

    `matrix[i][j]` is the flow from group i to group j. Undirected (the
    default), group i's arc is proportional to its row sum and is divided
    among its flows in column order; the ribbon between i and j joins i's
    share for `matrix[i][j]` to j's share for `matrix[j][i]`, so a
    symmetric matrix draws ribbons of equal width at both ends. With
    `directed=True` a group's arc is its row plus column sum, outgoing
    flows first, and each ribbon joins the source's outgoing share to the
    target's incoming share. `gap` is the angle in degrees between groups;
    `sort=True` orders each group's flows largest first.
    """
    m = _matrix(matrix)
    n = len(m)
    labels = [str(i) for i in range(n)] if names is None else [str(v) for v in names]
    if len(labels) != n:
        raise DiagramError(f"chord needs {n} names, got {len(labels)}")
    if directed:
        totals = [sum(m[i]) + sum(m[j][i] for j in range(n)) for i in range(n)]
    else:
        totals = [sum(m[i]) for i in range(n)]
    total = sum(totals)
    if total <= 0:
        raise DiagramError("a chord diagram needs at least one positive flow")
    live = sum(1 for t in totals if t > 0)
    if gap < 0 or gap * live >= 360:
        raise DiagramError(f"chord gap= of {gap} degrees leaves no room for the groups")
    per = (360.0 - gap * live) / total
    groups = []
    spans: dict[tuple[int, int, str], tuple[float, float]] = {}
    at = start
    for i in range(n):
        g0 = at
        order = list(range(n))
        if sort:
            order.sort(key=lambda j: -m[i][j])
        for j in order:
            if m[i][j] > 0:
                spans[(i, j, "out")] = (at, at + m[i][j] * per)
                at += m[i][j] * per
        if directed:
            incoming = list(range(n))
            if sort:
                incoming.sort(key=lambda j: -m[j][i])
            for j in incoming:
                if m[j][i] > 0:
                    spans[(i, j, "in")] = (at, at + m[j][i] * per)
                    at += m[j][i] * per
        groups.append(ChordGroup(labels[i], g0, at, totals[i]))
        if totals[i] > 0:
            at += gap
    ribbons = []
    for i in range(n):
        for j in range(n):
            if directed:
                if m[i][j] > 0:
                    ribbons.append(ChordRibbon(i, j, spans[(i, j, "out")], spans[(j, i, "in")],
                                               m[i][j], 0.0))
            elif j >= i and (m[i][j] > 0 or m[j][i] > 0):
                # A missing end is a point where the group's arc begins.
                a = spans.get((i, j, "out"), (groups[i].start,) * 2)
                b = a if i == j else spans.get((j, i, "out"), (groups[j].start,) * 2)
                ribbons.append(ChordRibbon(i, j, a, b, m[i][j], m[j][i]))
    return ChordLayout(tuple(groups), tuple(ribbons), total)


def _point(centre: Vec2, r: float, angle: float) -> Vec2:
    a = math.radians(angle)
    return centre + Vec2(math.cos(a), math.sin(a)) * r


def _quad_to(p0: Vec2, c: Vec2, p1: Vec2):
    return (p0, p0 + (c - p0) * (2 / 3), p1 + (c - p1) * (2 / 3), p1)


def _ribbon(centre: Vec2, r: float, a: tuple[float, float], b: tuple[float, float],
            head: float, **style) -> Diagram:
    """A ribbon from arc `a` to arc `b` at radius `r`, curving through the
    centre; `head > 0` points the `b` end like an arrow."""
    chain: list = []
    if a[1] - a[0] > 1e-9:
        chain.extend(arc_cubics(centre, r, a[0], a[1]))
        end_a = chain[-1][3]
    else:
        end_a = _point(centre, r, a[0])
    start_a = _point(centre, r, a[0])
    if head > 0:
        tip = _point(centre, r, (b[0] + b[1]) / 2)
        b0 = _point(centre, r - head, b[0])
        b1 = _point(centre, r - head, b[1])
        chain.append(_quad_to(end_a, centre, b0))
        if b[1] - b[0] > 1e-9:
            chain.append(straight_cubic(b0, tip))
            chain.append(straight_cubic(tip, b1))
        last = b1
    else:
        b0 = _point(centre, r, b[0])
        chain.append(_quad_to(end_a, centre, b0))
        if b[1] - b[0] > 1e-9:
            chain.extend(arc_cubics(centre, r, b[0], b[1]))
        last = chain[-1][3]
    chain.append(_quad_to(last, centre, start_a))
    return path(curves=tuple(chain), closed=True, kind=MARK_KIND, **style)


def _annulus(centre: Vec2, r0: float, r1: float, a0: float, a1: float, **style) -> Diagram:
    outer = list(arc_cubics(centre, r1, a0, a1))
    inner = arc_cubics(centre, r0, a1, a0)
    chain = outer + [straight_cubic(outer[-1][3], inner[0][0])] + list(inner)
    chain.append(straight_cubic(chain[-1][3], chain[0][0]))
    return path(curves=tuple(chain), closed=True, kind=MARK_KIND, **style)


def _outside(text: Diagram, centre: Vec2, r: float, angle: float) -> Vec2:
    """Where a horizontal label's centre goes to sit just outside radius `r`
    at `angle`: pushed out by its box's support distance."""
    a = math.radians(angle)
    u = Vec2(math.cos(a), math.sin(a))
    b = text.bbox
    push = r + abs(u.x) * b.width / 2 + abs(u.y) * b.height / 2
    return centre + u * push


def chord(panel, matrix, names=None, *, colors=None, gap: float = 2.0,
          start: float = -90.0, directed: bool = False, sort: bool = False,
          thickness: float | str | None = None, pad: float | str | None = None,
          labels: bool = True, opacity: float = 0.72, color_by: str = "source",
          size: float | str | None = None, **style) -> tuple[Diagram, dict]:
    """A chord diagram in `panel`'s plot area. See `Panel.chord`."""
    if color_by not in ("source", "target", "larger"):
        raise DiagramError(f'chord color_by is "source", "target" or "larger", not {color_by!r}')
    theme = active_theme()
    layout = chord_layout(matrix, names, gap=gap, start=start, directed=directed, sort=sort)
    n = len(layout.groups)
    font = theme.font_size_small if size is None else mm(size)
    from .hierarchy_plots import branch_colors
    if colors is None:
        fills = branch_colors(n, theme)
    elif isinstance(colors, str):
        fills = [colors] * n
    elif isinstance(colors, Mapping):
        auto = branch_colors(n, theme)
        fills = [str(colors.get(g.name, auto[k])) for k, g in enumerate(layout.groups)]
    else:
        fills = [str(c) for c in colors]
        if len(fills) < n:
            raise DiagramError(f"chord colors= has {len(fills)} colours for {n} groups")
    area = panel.area
    centre = area.center
    texts = [text_node(g.name, font, LABEL_KIND, markup=False) if labels and g.value > 0 else None
             for g in layout.groups]
    ring = min(area.width, area.height) * 0.045 if thickness is None else mm(thickness)
    clear = theme.gap("xs") if pad is None else mm(pad)
    # The largest radius whose labels still fit inside the area.
    radius = min(area.width, area.height) / 2 - ring
    for _ in range(30):
        worst = 0.0
        for g, t in zip(layout.groups, texts):
            if t is None:
                continue
            p = _outside(t, centre, radius + ring + clear, (g.start + g.end) / 2)
            b = t.bbox
            worst = max(worst, (abs(p.x - centre.x) + b.width / 2) - area.width / 2,
                        (abs(p.y - centre.y) + b.height / 2) - area.height / 2)
        if worst <= 1e-6:
            break
        radius -= worst
    if radius <= ring:
        raise DiagramError("the chord labels leave no room for the ring; widen the panel")
    inner = radius - clear * 0.4
    shapes: list = []
    for k, g in enumerate(layout.groups):
        if g.end - g.start > 1e-9:
            shapes.append(_annulus(centre, radius, radius + ring, g.start, g.end,
                                   fill=fills[k], stroke="none"))
    ribbons: list = []
    head = ring * 1.2 if directed else 0.0
    for rb in sorted(layout.ribbons, key=lambda r: -(r.value + r.back)):
        if color_by == "source":
            who = rb.source
        elif color_by == "target":
            who = rb.target
        else:
            who = rb.source if rb.value >= rb.back else rb.target
        paint = {"fill": fills[who], "fill_opacity": opacity,
                 "stroke": mix(fills[who], theme.ink, 0.35), "stroke_width": theme.hairline,
                 "stroke_opacity": min(1.0, opacity + 0.15)}
        paint.update(style)
        ribbons.append(_ribbon(centre, inner, rb.source_span, rb.target_span, head, **paint))
    words: list = []
    for g, t in zip(layout.groups, texts):
        if t is not None:
            words.append(draw_place([(_outside(t, centre, radius + ring + clear,
                                               (g.start + g.end) / 2), t)], origin=(0, 0)))
    node = draw_place(ribbons + shapes + words, origin=(0, 0), kind=abutting("chord"))
    note = {"groups": [(g.name, g.start, g.end, g.value) for g in layout.groups],
            "ribbons": [(r.source, r.target, r.value, r.back) for r in layout.ribbons],
            "radius": radius, "ring": ring, "total": layout.total,
            "colors": dict(zip((g.name for g in layout.groups), fills))}
    node.notes["chord"] = note
    return node, note


# -- arc diagram -----------------------------------------------------------------


def arc_diagram(panel, nodes, edges, *, sizes=None, top=None, diameter=None, floor=None,
                shape: str = "circle", shapes=None, groups=None, colors=None,
                color: str | None = None, labels: bool = True, rotate: float | None = None,
                weights=None, width=None, width_floor=None, edge_color=None,
                edge_colors=None, directed: bool = False, opacity: float = 0.8,
                size: float | str | None = None, **style) -> tuple[Diagram, dict]:
    """An arc diagram in `panel`'s plot area. See `Panel.arc_diagram`."""
    from .network import _node_values, encode, read_edges
    theme = active_theme()
    names, given = _node_values(nodes)
    if len(names) < 2:
        raise DiagramError("an arc diagram needs at least two nodes")
    if len(set(names)) != len(names):
        raise DiagramError("arc diagram node names repeat")
    values = dict(given)
    if sizes is not None:
        if not isinstance(sizes, Mapping):
            sizes = dict(zip(names, sizes))
        values.update({str(k): float(v) for k, v in sizes.items()})
    pairs = read_edges(edges, names)
    enc = encode(names, pairs, values=values, top=top, diameter=diameter, floor=floor,
                 shape=shape, shapes=shapes, groups=groups, colors=colors, color=color,
                 weights=weights, width=width, width_floor=width_floor,
                 edge_color=edge_color, edge_colors=edge_colors,
                 default_diameter=2.4 if values else 1.6)
    font = theme.font_size_small if size is None else mm(size)
    area = panel.area
    n = len(names)
    biggest = max(enc.diam)
    texts = [text_node(name, font, LABEL_KIND, markup=False) for name in names] if labels else []
    widest = max((t.bbox.width for t in texts), default=0.0)
    if rotate is None:
        rotate = 90.0 if widest > area.width / n * 0.92 else 0.0
    if texts and rotate:
        texts = [t.rotated(-rotate) for t in texts]
    room = max((t.bbox.height for t in texts), default=0.0)
    # The end nodes sit in from the edges by their own or their label's half
    # width, so the row spans the plot area.
    left = max(biggest / 2, texts[0].bbox.width / 2 if texts else 0.0)
    right = max(biggest / 2, texts[-1].bbox.width / 2 if texts else 0.0)
    pitch = (area.width - left - right) / (n - 1)
    if pitch <= biggest:
        raise DiagramError("the arc diagram's nodes do not fit side by side; widen the panel")
    xs = [area.x0 + left + pitch * k for k in range(n)]
    clear = theme.gap("xs")
    # The line of nodes sits on the labels, or in the middle of the room
    # above them for a directed diagram whose backward edges hang below.
    label_room = room + clear if texts else 0.0
    below = directed and any(u > v for u, v, _, _ in pairs)
    avail = area.height - label_room
    if below:
        base = area.y0 + avail / 2
        up = avail / 2 - clear
    else:
        base = area.y1 - label_room - biggest / 2
        up = base - area.y0
    spans = [abs(xs[v] - xs[u]) / 2 for u, v, _, _ in pairs if u != v]
    reach = max(spans, default=1.0)
    lift = min(1.0, up / reach) if reach > 0 else 1.0
    if lift <= 0:
        raise DiagramError("the arc diagram has no height for its arcs; make the panel taller")
    edge_nodes: list = []
    floored = 0
    for u, v, w, cat in sorted(pairs, key=lambda e: (e[2], e[0], e[1])):
        if u == v or w <= 0:
            continue
        a, b = sorted((xs[u], xs[v]))
        r = (b - a) / 2
        cx = (a + b) / 2
        sign = 1.0 if (not directed or u < v) else -1.0
        # A half ellipse `lift * r` tall from a to b: two exact quarter cubics.
        h = sign * lift * r
        k = 4 * (math.sqrt(2) - 1) / 3
        p0, top_, p1 = Vec2(a, base), Vec2(cx, base - h), Vec2(b, base)
        chain = ((p0, Vec2(a, base - h * k), Vec2(cx - r * k, base - h), top_),
                 (top_, Vec2(cx + r * k, base - h), Vec2(b, base - h * k), p1))
        ink = enc.cat_color.get(cat, enc.edge_ink) if cat is not None else enc.edge_ink
        stroke = enc.weights(w)
        floored += enc.weights.floored(w)
        paint = {"stroke": ink, "stroke_width": stroke, "fill": "none",
                 "stroke_opacity": opacity, "stroke_linecap": "butt"}
        paint.update(style)
        edge_nodes.append(path(curves=chain, kind=encoded(MARK_LINE_KIND), **paint))
    marks: list = []
    for k, (x, d, kind, fill) in enumerate(zip(xs, enc.diam, enc.kinds, enc.fills)):
        if kind == "square":
            side = d * math.sqrt(math.pi) / 2
            prim = RectPrim(side, side, side * 0.18)
        else:
            prim = EllipsePrim(d / 2, d / 2)
        marks.append((Vec2(x, base), Diagram(prim=prim, kind=MARK_KIND)
                      .styled(fill=fill, stroke=theme.paper, stroke_width=theme.hairline)))
    words: list = []
    for k, t in enumerate(texts):
        b = t.bbox
        top_y = area.y1 - room if below else base + biggest / 2 + clear
        words.append(draw_place([(Vec2(xs[k], top_y + b.height / 2), t)], origin=(0, 0)))
    node = draw_place(edge_nodes + marks + words, origin=(0, 0), kind=abutting("arc-diagram"))
    note = {"positions": dict(zip(names, xs)), "baseline": base, "lift": lift,
            "floored_edges": floored, "edges": len(pairs)}
    node.notes["arc_diagram"] = note
    return node, {"note": note, "widths": enc.weights, "sizes": enc.area,
                  "node_keys": [(g, enc.group_color[g],
                                 next(k for nm, k in zip(names, enc.kinds)
                                      if enc.group_of.get(nm) == g))
                                for g in enc.group_names],
                  "edge_keys": [(c, enc.cat_color[c]) for c in enc.categories]}
