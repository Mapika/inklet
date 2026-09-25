"""Weighted networks drawn from data: node sizes, edge widths and categories.

`inklet.graph` arranges boxes and routes arrows between them; it is for
diagrams. A network *plot* encodes numbers: a node's area is a value, an
edge's width is a weight, and colours are categories that a legend explains.
`Panel.network` draws one into a panel's plot area. Positions come from the
same solvers `inklet.graph` uses (`layout="force"`, `"layered"`, `"tree"`),
or from an even ring for `layout="circular"` -- the default, with its edges
bowed towards the centre so that chords between close neighbours stay
distinguishable from the rim.

    p = inklet.panel(50, 50)
    p.network(["a", "b", "c"], [("a", "b", 120), ("b", "c", 40, "inhibitory")],
              size={"a": 3, "b": 8, "c": 5})
    p.width_key(title="synapses").legend(side="bottom")

`WidthScale` is the weight-to-width mapping and `width_key` its key: lines
drawn at reference widths with their weights, the counterpart of
`size_key` for areas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, RectPrim, EllipsePrim, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import encoded, path, polygon, polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, MARK_LINE_KIND
from ..themes import contrast_ratio, readable
from ..themes.color import mix
from .axis import text_node, tick_texts
from .dotplot import AreaScale
from .scale import linear, nice_ticks

__all__ = ["WidthScale", "width_scale", "width_key", "network",
           "NETWORK_LAYOUTS", "NODE_SHAPES", "read_edges"]

NETWORK_LAYOUTS = ("circular", "force", "layered", "tree")
NODE_SHAPES = ("circle", "square")

WIDTH_KEY_KIND = "width-key"
LABEL_KIND = "label"

#: The rounding of a square node, as a fraction of its side.
_SQUARE_ROUND = 0.18
#: A square node's side, for the same area as the circle of its diameter.
_SQUARE_SIDE = math.sqrt(math.pi) / 2


@dataclass(frozen=True)
class WidthScale:
    """Weight to stroke width: `top` is drawn `width` mm wide and the width
    is proportional to the weight, but never thinner than `floor` mm, so a
    weak edge stays visible. The floor is a departure from proportionality
    and a key should show it; `width_key` does."""
    top: float
    width: float
    floor: float = 0.0

    def __post_init__(self) -> None:
        if not (math.isfinite(self.top) and self.top > 0):
            raise DiagramError(f"a width scale needs a positive top weight, got {self.top!r}")
        if not (math.isfinite(self.width) and self.width > 0):
            raise DiagramError(f"a width scale needs a positive width, got {self.width!r}")
        if not 0 <= self.floor <= self.width:
            raise DiagramError(f"a width scale's floor must be from 0 to its width, got {self.floor!r}")

    def __call__(self, weight: float) -> float:
        weight = float(weight)
        if not math.isfinite(weight) or weight < 0:
            raise DiagramError(f"an edge width cannot show weight {weight!r}")
        return max(self.floor, self.width * min(weight, self.top) / self.top)

    def floored(self, weight: float) -> bool:
        """Whether `weight` is drawn at the floor rather than to scale."""
        return self.width * float(weight) / self.top < self.floor

    def ticks(self, count: int = 3) -> tuple[float, ...]:
        """Round reference weights in (0, top], at most `count + 1` of them."""
        values: list[float] = []
        for asked in range(count, count + 4):
            values = [v for v in nice_ticks(0.0, self.top, asked) if v > 0]
            if len(values) >= count:
                break
        if len(values) > count + 1:
            values = values[::-1][::2][::-1]
        return tuple(values) or (self.top,)


def width_scale(top: float, width: float | str, floor: float | str = 0.0) -> WidthScale:
    """A `WidthScale`: weight `top` is drawn `width` mm wide."""
    return WidthScale(float(top), mm(width), mm(floor))


def width_key(scale: WidthScale, *, values: Sequence[float] | None = None,
              count: int = 3, format=None, title: str | None = None,
              color: str | None = None, length: float | str | None = None,
              font_size: float | str | None = None) -> Diagram:
    """Reference lines at the widths of `scale`, each with its weight.

    `values` names the reference weights (default: round values up to the
    scale's top); `format` is an axis format such as `"{:,.0f}"`. The lines
    are `length` mm long (default about 5 mm) in `color` (default: ink),
    stacked thickest first with the weights to their right; `title` goes
    above.
    """
    theme = active_theme()
    shown = sorted({float(v) for v in (scale.ticks(count) if values is None else values)},
                   reverse=True)
    if not shown or any(v <= 0 for v in shown):
        raise DiagramError("a width key needs positive reference weights")
    size = theme.font_size_small if font_size is None else mm(font_size)
    long = 5.0 if length is None else mm(length)
    ink = theme.ink if color is None else color
    texts = tick_texts(linear((0.0, scale.top)), shown, format)
    rows: list = []
    y = 0.0
    tall = text_node("0", size, LABEL_KIND).bbox.height
    step = max(tall + theme.gap("xs") * 0.6, scale.width + theme.gap("xs"))
    if title is not None:
        t = text_node(title, size, LABEL_KIND)
        rows.append(draw_place([(Vec2(t.bbox.width / 2, 0.0), t)], origin=(0, 0)))
        y += t.bbox.height / 2 + theme.gap("xs") + max(scale.width, size) / 2
    for value, text in zip(shown, texts):
        w = scale(value)
        rows.append(polyline(((0.0, y), (long, y)), kind=encoded(MARK_LINE_KIND), stroke=ink,
                             stroke_width=w, stroke_linecap="butt"))
        label = text_node(text, size, LABEL_KIND, features={"tnum": True})
        rows.append(draw_place([(Vec2(long + theme.gap("xs") + label.bbox.width / 2, y), label)],
                               origin=(0, 0)))
        y += step
    node = draw_place(rows, origin=(0, 0), kind=WIDTH_KEY_KIND)
    node.note("width_key", {"values": tuple(shown),
                            "widths": tuple(scale(v) for v in shown),
                            "top": scale.top, "width": scale.width, "floor": scale.floor})
    return node


# -- input ---------------------------------------------------------------------


def read_edges(edges, names: Sequence[str]) -> list[tuple[int, int, float, str | None]]:
    """`(source, target[, weight[, category]])` rows as index quadruples."""
    index = {name: k for k, name in enumerate(names)}
    out = []
    for position, edge in enumerate(edges):
        if not isinstance(edge, (tuple, list)) or not 2 <= len(edge) <= 4:
            raise DiagramError(
                f"network edge {position} is (source, target[, weight[, category]]), not {edge!r}")
        u, v = str(edge[0]), str(edge[1])
        for end in (u, v):
            if end not in index:
                raise DiagramError(f"network edge {position} names unknown node {end!r}")
        weight = 1.0
        if len(edge) >= 3 and edge[2] is not None:
            if isinstance(edge[2], bool) or not isinstance(edge[2], Real):
                raise DiagramError(f"network edge {position} weight must be a number, got {edge[2]!r}")
            weight = float(edge[2])
            if not math.isfinite(weight) or weight < 0:
                raise DiagramError(f"network edge {position} weight must be zero or more, got {edge[2]!r}")
        category = None if len(edge) < 4 or edge[3] is None else str(edge[3])
        out.append((index[u], index[v], weight, category))
    return out


def _node_values(nodes) -> tuple[list[str], dict[str, float]]:
    if isinstance(nodes, Mapping):
        names = [str(k) for k in nodes]
        values = {}
        for k, v in nodes.items():
            if v is not None:
                if isinstance(v, bool) or not isinstance(v, Real) or v < 0:
                    raise DiagramError(f"network node {k!r} value must be a number of zero or more")
                values[str(k)] = float(v)
        return names, values
    names = [str(n) for n in nodes]
    return names, {}


# -- geometry ------------------------------------------------------------------


def _quad_point(p0: Vec2, c: Vec2, p1: Vec2, t: float) -> Vec2:
    a = 1 - t
    return p0 * (a * a) + c * (2 * a * t) + p1 * (t * t)


def _quad_split(p0: Vec2, c: Vec2, p1: Vec2, t0: float, t1: float) -> tuple[Vec2, Vec2, Vec2]:
    """The part of a quadratic Bezier between parameters t0 and t1."""
    q0 = _quad_point(p0, c, p1, t0)
    q1 = _quad_point(p0, c, p1, t1)
    # The tangent at t, scaled: d/dt = 2[(1-t)(c-p0) + t(p1-c)].
    d0 = (c - p0) * (1 - t0) + (p1 - c) * t0
    qc = q0 + d0 * (t1 - t0)
    return q0, qc, q1


def _exit(p0: Vec2, c: Vec2, p1: Vec2, centre: Vec2, reach: float, from_start: bool) -> float:
    """The parameter where the curve leaves the disc of `reach` around `centre`."""
    lo, hi = (0.0, 0.5) if from_start else (0.5, 1.0)
    def inside(t: float) -> bool:
        return (_quad_point(p0, c, p1, t) - centre).length < reach

    if from_start:
        if not inside(0.0):
            return 0.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if inside(mid):
                lo = mid
            else:
                hi = mid
        return hi
    if not inside(1.0):
        return 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if inside(mid):
            hi = mid
        else:
            lo = mid
    return lo


def _cubic_of(q0: Vec2, qc: Vec2, q1: Vec2) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    return (q0, q0 + (qc - q0) * (2 / 3), q1 + (qc - q1) * (2 / 3), q1)


def _positions(names, diam, layout, pairs, order, gap, iterations):
    """Unit positions for every node, centred on the origin."""
    n = len(names)
    if layout == "circular":
        sequence = list(range(n)) if order is None else [names.index(str(o)) for o in order]
        if order is not None and sorted(sequence) != list(range(n)):
            raise DiagramError("network order= must list every node once")
        out = [Vec2(0, 0)] * n
        for slot, k in enumerate(sequence):
            angle = -math.pi / 2 + 2 * math.pi * slot / n
            out[k] = Vec2(math.cos(angle), math.sin(angle))
        return out
    from ..core import resolve
    from ..layout.graph import graph as make_graph
    boxes = [Diagram(prim=RectPrim(d, d), kind="network-slot") for d in diam]
    simple = sorted({(u, v) for u, v, _, _ in pairs if u != v})
    g = make_graph(boxes, simple, layout=layout, gap=gap, iterations=iterations)
    placed = {id(x.diagram): x for x in resolve(g.diagram).values()}
    out = [placed[id(box)].bbox.center for box in boxes]
    cx = sum(p.x for p in out) / n
    cy = sum(p.y for p in out) / n
    return [Vec2(p.x - cx, p.y - cy) for p in out]


@dataclass
class Encoding:
    """How a network's numbers and categories become sizes and colours."""
    diam: list
    area: AreaScale | None
    kinds: list
    fills: list
    group_names: list
    group_color: dict
    group_of: dict
    weights: WidthScale
    edge_ink: str
    categories: list
    cat_color: dict


def encode(names, pairs, *, values, top=None, diameter=None, floor=None, shape="circle",
           shapes=None, groups=None, color=None, weights=None, width=None,
           width_floor=None, edge_color=None, default_diameter: float | None = None) -> Encoding:
    """Node diameters (area proportional to value, with a floor), node
    shapes and fills, and edge widths and category colours, shared by
    `network` and `arc_diagram`.

    `color` is one colour (the fill of ungrouped nodes) or a mapping of node
    or group names to colours; `edge_color` is one colour (uncategorised
    edges), a mapping of edge categories to colours, or a sequence of
    colours taken by the categories in order."""
    theme = active_theme()
    if color is not None and not isinstance(color, (str, Mapping)):
        raise DiagramError(f"network color= is one colour or a mapping, not {color!r}")
    colors = color if isinstance(color, Mapping) else None
    color = color if isinstance(color, str) else None
    edge_colors = None if edge_color is None or isinstance(edge_color, str) else edge_color
    edge_color = edge_color if isinstance(edge_color, str) else None
    # Node diameters: area proportional to value, with a floor.
    dmax = ((4.0 if values else 2.2) if default_diameter is None else default_diameter) \
        if diameter is None else mm(diameter)
    dmin = min(dmax, 1.2 if floor is None else mm(floor))
    area = None
    if values:
        highest = max(values.values()) if top is None else float(top)
        area = AreaScale(highest if highest > 0 else 1.0, dmax)
    diam = []
    for name in names:
        v = values.get(name)
        diam.append(dmax if v is None or area is None else max(dmin, area(v)))

    # Node shapes and colours.
    def pick(source, name, default):
        if source is None:
            return default
        if isinstance(source, str):
            return source
        if isinstance(source, Mapping):
            if name in source:
                return str(source[name])
            group = None if groups is None else groups.get(name)
            if group is not None and group in source:
                return str(source[group])
            return default
        raise DiagramError(f"expected a mapping or a single value, got {source!r}")

    group_of = {} if groups is None else {str(k): str(v) for k, v in groups.items()}
    group_names = []
    for name in names:
        g = group_of.get(name)
        if g is not None and g not in group_names:
            group_names.append(g)
    from .hierarchy_plots import branch_colors
    group_color = dict(zip(group_names, branch_colors(len(group_names), theme)))
    if isinstance(colors, Mapping):
        group_color.update({g: str(colors[g]) for g in group_names if g in colors})
    base = mix(theme.muted, theme.paper, 0.45) if color is None else color
    fills = []
    kinds = []
    for name in names:
        default = group_color.get(group_of.get(name), base)
        fills.append(pick(colors, name, default))
        kinds.append(pick(shapes, name, shape))
    for k in kinds:
        if k not in NODE_SHAPES:
            raise DiagramError(f"network node shape is circle or square, not {k!r}")

    # Edge widths.
    if weights is None:
        heaviest = max((w for _, _, w, _ in pairs), default=1.0) or 1.0
        wmax = 1.6 if width is None else mm(width)
        wmin = min(wmax, theme.hairline if width_floor is None else mm(width_floor))
        weights = WidthScale(heaviest, wmax, wmin)
    edge_ink = mix(theme.muted, theme.paper, 0.2) if edge_color is None else edge_color
    categories = []
    for *_, cat in pairs:
        if cat is not None and cat not in categories:
            categories.append(cat)
    if isinstance(edge_colors, Mapping):
        cat_color = {c: str(edge_colors.get(c, edge_ink)) for c in categories}
    elif edge_colors is None:
        # Edge categories take palette slots after the node groups'.
        cat_color = {c: theme.ink_color(len(group_names) + k) for k, c in enumerate(categories)}
    else:
        palette = list(edge_colors)
        cat_color = {c: palette[k % len(palette)] for k, c in enumerate(categories)}

    return Encoding(diam, area, kinds, fills, group_names, group_color, group_of,
                    weights, edge_ink, categories, cat_color)


def node_values(names, given, size, who: str) -> dict:
    """Node values from the `nodes` mapping, overridden by `size=` (a
    mapping by node name, one value per node, or one value for every node)."""
    values = dict(given)
    if size is None:
        return values
    if isinstance(size, Real):
        return {name: float(size) for name in names}
    if not isinstance(size, Mapping):
        size = dict(zip(names, size))
    for k, v in size.items():
        if str(k) not in names:
            raise DiagramError(f"{who} size= names unknown node {k!r}")
        values[str(k)] = float(v)
    return values


def network(panel, nodes, edges, *, layout: str = "circular", order=None,
            size=None, top: float | None = None, diameter: float | str | None = None,
            floor: float | str | None = None, shape: str = "circle", shapes=None,
            groups=None, color=None, labels="auto",
            label_size: float | str | None = None,
            weights: WidthScale | None = None, width: float | str | None = None,
            width_floor: float | str | None = None, edge_color=None, bend: float | None = None, arrows: bool = False,
            opacity: float = 0.85, gap: float | str | None = None,
            iterations: int = 300, **style) -> tuple[Diagram, dict]:
    """A weighted network in `panel`'s plot area. See `Panel.network`."""
    if layout not in NETWORK_LAYOUTS:
        raise DiagramError(f"network layout is one of {', '.join(NETWORK_LAYOUTS)}, not {layout!r}")
    theme = active_theme()
    names, given = _node_values(nodes)
    if not names:
        raise DiagramError("a network needs at least one node")
    if len(set(names)) != len(names):
        raise DiagramError("network node names repeat")
    values = node_values(names, given, size, "network")
    pairs = read_edges(edges, names)
    font = theme.font_size_small if label_size is None else mm(label_size)

    enc = encode(names, pairs, values=values, top=top, diameter=diameter, floor=floor,
                 shape=shape, shapes=shapes, groups=groups, color=color,
                 weights=weights, width=width, width_floor=width_floor,
                 edge_color=edge_color)
    diam, area, kinds, fills = enc.diam, enc.area, enc.kinds, enc.fills
    group_names, group_color, group_of = enc.group_names, enc.group_color, enc.group_of
    weights, edge_ink, categories, cat_color = enc.weights, enc.edge_ink, enc.categories, enc.cat_color

    # Labels: inside when they fit in the node, otherwise outside.
    label_nodes = []
    for name, d, kind, fill in zip(names, diam, kinds, fills):
        if labels is False or labels is None:
            label_nodes.append(None)
            continue
        text = text_node(name, font, LABEL_KIND, markup=False)
        room = d * (_SQUARE_SIDE if kind == "square" else 0.72)
        inside = labels == "inside" or (labels == "auto" and text.bbox.width <= room * 0.95
                                        and text.bbox.height <= room)
        if labels == "outside":
            inside = False
        label_nodes.append((text, inside))

    # Fit the unit layout into the area, leaving room for nodes and labels.
    box = panel.area
    unit = _positions(names, diam, layout, pairs, order, theme.gap("m") if gap is None else mm(gap),
                      iterations)
    margin_x = margin_y = 0.0
    for d, lab in zip(diam, label_nodes):
        margin_x = max(margin_x, d / 2)
        margin_y = max(margin_y, d / 2)
        if lab is not None and not lab[1]:
            margin_x = max(margin_x, d / 2 + theme.gap("xs") + lab[0].bbox.width)
            margin_y = max(margin_y, d / 2 + theme.gap("xs") + lab[0].bbox.height)
    span_x = max((abs(p.x) for p in unit), default=0.0)
    span_y = max((abs(p.y) for p in unit), default=0.0)
    sx = (box.width / 2 - margin_x) / span_x if span_x > 1e-12 else math.inf
    sy = (box.height / 2 - margin_y) / span_y if span_y > 1e-12 else math.inf
    if layout == "circular":
        # A ring stays round.
        sx = sy = min(sx, sy)
    else:
        # A force or layered drawing has no aspect of its own: it fills the area.
        sx = sy if not math.isfinite(sx) else sx
        sy = sx if not math.isfinite(sy) else sy
    if not math.isfinite(sx):
        sx = sy = 0.0
    if (sx <= 0 or sy <= 0) and len(names) > 1:
        raise DiagramError("the network's nodes and labels do not fit in the panel; "
                           "make the panel larger or the nodes smaller")
    centre = box.center
    at = [centre + Vec2(p.x * sx, p.y * sy) for p in unit]

    # Edges, lightest first so the heavy ones read on top.
    reach = [d / 2 * (1.12 if k == "square" else 1.0) for d, k in zip(diam, kinds)]
    present = {(u, v) for u, v, _, _ in pairs}
    edge_nodes = []
    floored = 0
    for u, v, w, cat in sorted(pairs, key=lambda e: (e[2], e[0], e[1])):
        if u == v or w <= 0:
            continue
        a, b = at[u], at[v]
        chord = b - a
        length = chord.length
        if length <= 1e-9:
            continue
        normal = Vec2(-chord.y / length, chord.x / length)
        mid = (a + b) * 0.5
        if layout == "circular" and not ((v, u) in present and arrows):
            toward = centre - mid
            sign = 1.0 if normal.dot(toward) >= 0 else -1.0
            if toward.length < 1e-9:
                sign = 1.0
        else:
            sign = 1.0
        bow = (0.25 if layout == "circular" else 0.0) if bend is None else float(bend)
        if (v, u) in present and arrows and bow == 0.0:
            bow = 0.12
        control = mid + normal * (sign * bow * length)
        t0 = _exit(a, control, b, a, reach[u] + theme.hairline, True)
        t1 = _exit(a, control, b, b, reach[v] + theme.hairline, False)
        if t1 <= t0:
            continue
        stroke = weights(w)
        floored += weights.floored(w)
        ink = cat_color.get(cat, edge_ink) if cat is not None else edge_ink
        head = None
        if arrows:
            # The head occupies the last part of the curve; the shaft stops at
            # its base so the line does not poke through the tip.
            head_len = max(theme.arrow_size * 0.8, stroke * 2.6)
            tip = _quad_point(a, control, b, t1)
            lo_t, hi_t = t0, t1
            for _ in range(40):
                mid_t = (lo_t + hi_t) / 2
                if (tip - _quad_point(a, control, b, mid_t)).length > head_len:
                    lo_t = mid_t
                else:
                    hi_t = mid_t
            base_t = lo_t
            base = _quad_point(a, control, b, base_t)
            direction = (tip - base)
            if direction.length > 1e-9:
                direction = direction * (1 / direction.length)
                side = Vec2(-direction.y, direction.x) * (max(stroke * 1.9, head_len * 0.36))
                head = polygon((tip, base + side, base - side), kind=MARK_KIND, fill=ink,
                               stroke="none", fill_opacity=opacity)
            t1 = base_t + (t1 - base_t) * 0.15
        q0, qc, q1 = _quad_split(a, control, b, t0, t1)
        curve = _cubic_of(q0, qc, q1)
        paint = {"stroke": ink, "stroke_width": stroke, "fill": "none",
                 "stroke_linecap": "butt", "stroke_opacity": opacity}
        paint.update(style)
        edge_nodes.append(path(curves=(curve,), kind=encoded(MARK_LINE_KIND), **paint))
        if head is not None:
            edge_nodes.append(head)

    # Nodes and labels.
    node_items = []
    text_items = []
    outline = {"stroke": theme.paper, "stroke_width": theme.hairline}
    for k, (name, d, kind, fill, lab) in enumerate(zip(names, diam, kinds, fills, label_nodes)):
        if kind == "square":
            side = d * _SQUARE_SIDE * 1.12
            prim = RectPrim(side, side, side * _SQUARE_ROUND)
        else:
            prim = EllipsePrim(d / 2, d / 2)
        shape_node = Diagram(prim=prim, kind=MARK_KIND).styled(fill=fill, **outline)
        node_items.append((at[k], shape_node))
        if lab is None:
            continue
        text, inside = lab
        if inside:
            ink = theme.ink if contrast_ratio(theme.ink, fill) >= contrast_ratio(theme.paper, fill) \
                else theme.paper
            if contrast_ratio(ink, fill) < 4.5:
                ink = readable(ink, fill, 4.5)
            text = text.styled(text_fill=ink)
            text_items.append((at[k], text))
        else:
            out = at[k] - centre
            if out.length < 1e-9:
                out = Vec2(1.0, 0.0)
            direction = out * (1 / out.length)
            tb = text.bbox
            clear = d / 2 + theme.gap("xs")
            # Push the label's box off the node along the outward direction:
            # the support distance of a box in direction u is |ux|w/2 + |uy|h/2.
            push = clear + abs(direction.x) * tb.width / 2 + abs(direction.y) * tb.height / 2
            text_items.append((at[k] + direction * push, text))
    group = draw_place(edge_nodes + node_items + text_items, origin=(0, 0),
                       kind=abutting("network"))
    note = {"positions": {name: (round(p.x, 6), round(p.y, 6)) for name, p in zip(names, at)},
            "diameters": dict(zip(names, diam)), "widths": weights,
            "floored_edges": floored, "edges": len(pairs), "layout": layout,
            "categories": dict(cat_color), "groups": dict(group_color),
            "sizes": area}
    group.notes["network"] = {k: v for k, v in note.items() if k not in ("widths", "sizes")}
    keys = [(g, group_color[g], _shape_of(g, names, group_of, kinds)) for g in group_names]
    note["node_keys"] = keys
    note["edge_keys"] = [(c, cat_color[c]) for c in categories]
    return group, note


def _shape_of(group, names, group_of, kinds) -> str:
    for name, kind in zip(names, kinds):
        if group_of.get(name) == group:
            return kind
    return "circle"
