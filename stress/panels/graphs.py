"""Three panels inklet has no idiom for: a graph, a state machine, a caption.

`panel_o` is the one the spec calls the known ceiling. inklet routes edges but
does not *place* nodes: there is no ELK, no dagre, no force-directed solver, no
layering. So the layering, the crossing reduction and the coordinate assignment
are written here, in the block between the two BEGIN/END banners, and the
number of lines that block costs is the finding -- see `layout_cost()`.

`panel_p` reuses the same engine for a state machine, which is a graph too, and
then hits the second wall: inklet's connectors are straight, elbowed or
obstacle-avoiding, and none of those can be a self-loop, one of two separated
reciprocal arcs, or a label riding on a curve. Those are drawn here too.

`panel_r` is the caption block, and it is *meant* to look broken in places.
Its job is to show what inklet's text layer does with scripts it cannot measure.
`caption_metrics()` reports the damage in millimetres so a composed figure can
say so out loud rather than hoping the reader notices.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

import inklet
from inklet.core import Envelope, Rect, Vec2
from inklet.draw.path import catmull_rom
from inklet.typeset import shape

__all__ = ["panel_o", "panel_p", "panel_r", "caption_metrics", "layout_cost"]

Cubic = tuple[Vec2, Vec2, Vec2, Vec2]


# =====  BEGIN layered graph layout  =========================================
# A Sugiyama-style layout: layers are given (this is an anatomical hierarchy,
# not something to infer), edges spanning more than one layer are split over
# invisible nodes, the order within each layer is settled by barycentre sweeps,
# and the cross-axis coordinate is a barycentre pass with a separation
# constraint so that no two boxes touch. Everything is in millimetres and
# everything is deterministic: no dict iteration order, no randomness, no ties
# broken by chance.


@dataclass(frozen=True)
class Edge:
    """A directed, weighted edge. `weight` is data, not geometry."""

    src: str
    dst: str
    weight: float = 1.0
    kind: str = "forward"


@dataclass(frozen=True)
class Layout:
    """Where the layout put things, in (cross, flow) millimetres.

    `flow` grows with the layer index; a caller maps the pair onto the page,
    which is how one engine serves a bottom-up hierarchy and a left-to-right
    state machine without either of them knowing about the other.
    """

    pos: dict[str, Vec2]
    bends: dict[int, tuple[str, ...]]   # edge index -> its dummy nodes, in order
    layers: tuple[tuple[str, ...], ...]
    crossings: int
    naive_crossings: int


def layered(order: Sequence[str], level: Mapping[str, int], edges: Sequence[Edge],
            *, cross: Mapping[str, float], flow: Mapping[str, float],
            cross_gap: float, flow_gap: float, sweeps: int = 24) -> Layout:
    """Lay a levelled digraph out. `order` is the author's declaration order,
    which is also the naive ordering the result is scored against."""
    depth = dict(level)
    layers = _seed(order, depth)
    segments, chains = _expand(layers, depth, edges)
    span_c = {key: cross.get(key, 0.0) for key in depth}
    span_f = {key: flow.get(key, 0.0) for key in depth}

    naive = _crossings(layers, depth, segments)
    ordered, crossings = _reorder(layers, depth, segments, sweeps)
    across = _spread(ordered, depth, segments, span_c, cross_gap)
    along = _along(ordered, span_f, flow_gap)

    pos = {key: Vec2(across[key], along[depth[key]]) for key in depth}
    return Layout(pos, chains, tuple(tuple(row) for row in ordered),
                  crossings, naive)


def fit_gap(span: Callable[[float], float], target: float,
            lo: float, hi: float, *, tol: float = 0.02) -> float:
    """Pick the in-layer gap that makes a layout exactly `target` across.

    A layout engine that cannot be asked for a width is only half an engine:
    the caller has a column to fill, not a spacing preference. `span` must not
    shrink as the gap grows -- separation-constrained coordinates never do --
    so bisection is enough, and the bracket carries the taste: below `lo` the
    boxes crowd, above `hi` a small graph scatters into confetti.
    """
    if span(hi) <= target:
        return hi
    if span(lo) >= target:
        return lo
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if span(mid) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def extent(layout: "Layout", size: Mapping[str, float], axis: str = "x") -> float:
    """How wide the laid-out boxes actually are along one axis, dummies and
    all. `size` is the box measurement on that same axis."""
    values = [(getattr(pos, axis), size.get(key, 0.0))
              for key, pos in layout.pos.items()]
    return (max(v + w / 2 for v, w in values)
            - min(v - w / 2 for v, w in values))


def _seed(order: Sequence[str], depth: dict[str, int]) -> list[list[str]]:
    layers: list[list[str]] = [[] for _ in range(max(depth.values()) + 1)]
    for key in order:
        layers[depth[key]].append(key)
    return layers


def _expand(layers: list[list[str]], depth: dict[str, int],
            edges: Sequence[Edge]) -> tuple[list[tuple[str, str]], dict[int, tuple[str, ...]]]:
    """Split every edge that skips a layer over invisible nodes.

    Without this a long edge is invisible to the crossing counter -- it is not
    an edge between adjacent layers -- and the ordering that minimises the
    count would happily drive it through three boxes.
    """
    seen: set[tuple[str, str]] = set()
    segments: list[tuple[str, str]] = []
    chains: dict[int, tuple[str, ...]] = {}
    for index, edge in enumerate(edges):
        here, there = depth[edge.src], depth[edge.dst]
        step = 1 if there > here else -1
        chain: list[str] = []
        for k, lv in enumerate(range(here + step, there, step)):
            key = f"·{index}.{k}"
            depth[key] = lv
            layers[lv].append(key)
            chain.append(key)
        chains[index] = tuple(chain)
        walk = (edge.src, *chain, edge.dst)
        for a, b in zip(walk, walk[1:]):
            pair = (a, b) if a < b else (b, a)
            if pair not in seen:      # a reciprocal pair is one line, not two
                seen.add(pair)
                segments.append((a, b))
    return segments, chains


def _crossings(layers: Sequence[Sequence[str]], depth: Mapping[str, int],
               segments: Sequence[tuple[str, str]]) -> int:
    """Edge crossings between adjacent layers, the quantity being minimised."""
    rank = {key: i for row in layers for i, key in enumerate(row)}
    gaps: dict[int, list[tuple[int, int]]] = {}
    for u, v in segments:
        upper, lower = (u, v) if depth[u] < depth[v] else (v, u)
        gaps.setdefault(min(depth[u], depth[v]), []).append((rank[upper], rank[lower]))
    total = 0
    for pairs in gaps.values():
        for i, (a1, b1) in enumerate(pairs):
            for a2, b2 in pairs[i + 1:]:
                total += (a1 - a2) * (b1 - b2) < 0
    return total


def _neighbours(segments: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for u, v in segments:
        out.setdefault(u, []).append(v)
        out.setdefault(v, []).append(u)
    return out


def _reorder(layers: list[list[str]], depth: Mapping[str, int],
             segments: Sequence[tuple[str, str]],
             sweeps: int) -> tuple[list[list[str]], int]:
    """Barycentre sweeps, alternating direction, keeping the best seen.

    Barycentre ordering is not monotone -- a sweep can make things worse -- so
    the running best is kept rather than the last state, which is the
    difference between a reliable improvement and a coin flip.
    """
    near = _neighbours(segments)
    current = [list(row) for row in layers]
    best, score = [list(row) for row in current], _crossings(current, depth, segments)
    for sweep in range(sweeps):
        down = sweep % 2 == 0
        steps = range(1, len(current)) if down else range(len(current) - 2, -1, -1)
        for i in steps:
            rank = {key: j for j, key in enumerate(current[i - 1 if down else i + 1])}
            keyed = []
            for j, key in enumerate(current[i]):
                seen = [rank[n] for n in near.get(key, ()) if n in rank]
                keyed.append(((sum(seen) / len(seen) if seen else float(j), j), key))
            current[i] = [key for _, key in sorted(keyed)]
        found = _crossings(current, depth, segments)
        if found < score:
            best, score = [list(row) for row in current], found
    return best, score


def _spread(layers: Sequence[Sequence[str]], depth: Mapping[str, int],
            segments: Sequence[tuple[str, str]], span: Mapping[str, float],
            gap: float, passes: int = 12) -> dict[str, float]:
    """Cross-axis coordinates: pull each node towards its neighbours' mean,
    then push the layer apart again until nothing overlaps."""
    near = _neighbours(segments)
    across: dict[str, float] = {}
    for row in layers:
        total = sum(span[key] for key in row) + gap * (len(row) - 1)
        cursor = -total / 2
        for key in row:
            across[key] = cursor + span[key] / 2
            cursor += span[key] + gap
    for run in range(passes):
        down = run % 2 == 0
        steps = range(1, len(layers)) if down else range(len(layers) - 2, -1, -1)
        for i in steps:
            anchor = set(layers[i - 1 if down else i + 1])
            want = {}
            for key in layers[i]:
                seen = [across[n] for n in near.get(key, ()) if n in anchor]
                want[key] = sum(seen) / len(seen) if seen else across[key]
            _separate(layers[i], want, span, gap, across)
    return across


def _separate(row: Sequence[str], want: Mapping[str, float],
              span: Mapping[str, float], gap: float,
              across: dict[str, float]) -> None:
    """Left-to-right feasibility, then slide the whole layer back onto the
    centre of mass it wanted. Enforcing from one side alone biases everything
    rightward; the shift takes that bias out without breaking the constraint,
    which a second right-to-left pass would."""
    if not row:
        return
    place = [want[key] for key in row]
    for i in range(1, len(row)):
        floor = place[i - 1] + (span[row[i - 1]] + span[row[i]]) / 2 + gap
        place[i] = max(place[i], floor)
    drift = (sum(want[key] for key in row) - sum(place)) / len(row)
    for key, value in zip(row, place):
        across[key] = value + drift


def _along(layers: Sequence[Sequence[str]], span: Mapping[str, float],
           gap: float) -> list[float]:
    """Flow-axis coordinate per layer: `gap` of clear space between the near
    faces of the thickest node in one layer and the thickest in the next."""
    out: list[float] = []
    cursor = previous = 0.0
    for i, row in enumerate(layers):
        thick = max((span[key] for key in row), default=0.0)
        if i:
            cursor += previous / 2 + gap + thick / 2
        out.append(cursor)
        previous = thick
    return out


# =====  END layered graph layout  ===========================================


def layout_cost() -> dict[str, int]:
    """How much code the missing layout module cost, measured not guessed."""
    import pathlib

    lines = pathlib.Path(__file__).read_text(encoding="utf-8").splitlines()
    start = next(i for i, s in enumerate(lines) if s.startswith("# =====  BEGIN"))
    end = next(i for i, s in enumerate(lines) if s.startswith("# =====  END"))
    block = lines[start + 1:end]
    code = [s for s in block if s.strip() and not s.strip().startswith("#")]
    return {"total": len(block), "code_or_docstring": len(code)}


# ---------------------------------------------------------------------------
# Curved connectors. inklet.links draws straight, elbowed and orthogonally
# detoured shafts; a graph wants smooth ones, a reciprocal pair wants two of
# them bowed apart, and a state machine wants a loop that comes back to where
# it started. None of that is expressible, so it is built from inklet.path.
# ---------------------------------------------------------------------------

_SAMPLES = 16          # per cubic, when hunting for a boundary crossing
_HEAD_HALF = 0.36      # of head length, matching inklet.links' own arrowhead


def _at(chain: Sequence[Cubic], u: float) -> Vec2:
    i = max(0, min(int(u), len(chain) - 1))
    return _bezier(chain[i], min(max(u - i, 0.0), 1.0))


def _bezier(cubic: Cubic, t: float) -> Vec2:
    p0, c1, c2, p3 = cubic
    s = 1.0 - t
    return (p0 * (s * s * s) + c1 * (3 * s * s * t)
            + c2 * (3 * s * t * t) + p3 * (t * t * t))


def _tangent(chain: Sequence[Cubic], u: float) -> Vec2:
    step = 1e-4
    a = _at(chain, max(0.0, u - step))
    b = _at(chain, min(len(chain), u + step))
    delta = b - a
    return delta.normalized() if delta.length > 1e-12 else Vec2(1.0, 0.0)


def _split(cubic: Cubic, t: float) -> tuple[Cubic, Cubic]:
    """de Casteljau, so a trimmed curve is still exactly the same curve."""
    p0, c1, c2, p3 = cubic
    a = p0 + (c1 - p0) * t
    b = c1 + (c2 - c1) * t
    c = c2 + (p3 - c2) * t
    d = a + (b - a) * t
    e = b + (c - b) * t
    f = d + (e - d) * t
    return (p0, a, d, f), (f, e, c, p3)


def _after(chain: Sequence[Cubic], u: float) -> tuple[Cubic, ...]:
    i = max(0, min(int(u), len(chain) - 1))
    t = min(max(u - i, 0.0), 1.0)
    if t <= 1e-9:
        return tuple(chain[i:])
    if t >= 1.0 - 1e-9:
        return tuple(chain[i + 1:]) or (chain[-1],)
    return (_split(chain[i], t)[1],) + tuple(chain[i + 1:])


def _before(chain: Sequence[Cubic], u: float) -> tuple[Cubic, ...]:
    i = max(0, min(int(u), len(chain) - 1))
    t = min(max(u - i, 0.0), 1.0)
    if t >= 1.0 - 1e-9:
        return tuple(chain[:i + 1])
    if t <= 1e-9:
        return tuple(chain[:i]) or (chain[0],)
    return tuple(chain[:i]) + (_split(chain[i], t)[0],)


def _shift(box: Rect, by: Vec2) -> Rect:
    """`Rect` has union, pad, overlap and transform but no translate, and a
    node's bbox comes back in its own frame, so every placed box needs this."""
    return Rect(box.x0 + by.x, box.y0 + by.y, box.x1 + by.x, box.y1 + by.y)


def _leave(chain: Sequence[Cubic], box: Rect | None, standoff: float) -> float:
    """Where the curve last leaves `box`, as a global parameter."""
    if box is None:
        return 0.0
    grown = box.pad(standoff)
    last = 0.0
    for k in range(len(chain) * _SAMPLES + 1):
        u = k / _SAMPLES
        if grown.contains(_at(chain, u)):
            last = u
    return last


def _reach(chain: Sequence[Cubic], box: Rect | None, standoff: float) -> float:
    if box is None:
        return float(len(chain))
    grown = box.pad(standoff)
    for k in range(len(chain) * _SAMPLES + 1):
        u = k / _SAMPLES
        if grown.contains(_at(chain, u)):
            return u
    return float(len(chain))


def _clip(chain: Sequence[Cubic], src: Rect | None, dst: Rect | None,
          standoff: float = 0.0) -> tuple[Cubic, ...]:
    """Trim a curve back to the boundaries of the two shapes it joins.

    inklet.links does this with `Trace.exit`, which fires one straight ray; a
    curve can leave a rounded box, re-enter it and leave again, so the answer
    has to come from walking the curve rather than from a single ray.
    """
    end = _reach(chain, dst, standoff)
    cut = _before(chain, end) if end < len(chain) else tuple(chain)
    start = _leave(cut, src, standoff)
    return _after(cut, start) if start > 0.0 else cut


def _walk(chain: Sequence[Cubic], steps: int = _SAMPLES) -> list[tuple[float, float]]:
    """(parameter, cumulative length) samples along a chain."""
    out = [(0.0, 0.0)]
    total = 0.0
    previous = _at(chain, 0.0)
    for k in range(1, len(chain) * steps + 1):
        u = k / steps
        point = _at(chain, u)
        total += (point - previous).length
        out.append((u, total))
        previous = point
    return out


def _strand(chain: Sequence[Cubic], steps: int = 12) -> tuple[Vec2, ...]:
    """A curve reduced to a handful of points, which is all an obstacle test
    needs and far closer to the truth than the curve's bounding box."""
    return tuple(_bezier(cubic, i / steps)
                 for cubic in chain for i in range(steps + 1))


def _length(chain: Sequence[Cubic]) -> float:
    return _walk(chain)[-1][1]


def _param_at(chain: Sequence[Cubic], distance: float) -> float:
    samples = _walk(chain)
    target = min(max(distance, 0.0), samples[-1][1])
    for (u0, d0), (u1, d1) in zip(samples, samples[1:]):
        if d1 >= target:
            share = 0.0 if d1 - d0 < 1e-12 else (target - d0) / (d1 - d0)
            return u0 + (u1 - u0) * share
    return samples[-1][0]


def _shorten(chain: Sequence[Cubic], amount: float) -> tuple[Cubic, ...]:
    """Pull the far end back, so a shaft stops where its arrowhead starts."""
    total = _length(chain)
    if amount <= 0 or total <= amount * 1.05:
        return tuple(chain)
    return _before(chain, _param_at(chain, total - amount))


def _bow(a: Vec2, b: Vec2, offset: float) -> tuple[Cubic, ...]:
    """One cubic from a to b, bowed `offset` mm to the left of the chord.

    This is what separates a reciprocal pair: the same two boxes, two arcs,
    equal and opposite offsets, so neither hides the other.
    """
    chord = b - a
    normal = Vec2(chord.y, -chord.x).normalized() if chord.length > 1e-12 else Vec2(0, -1)
    lift = normal * offset
    return ((a, a + chord * (1 / 3) + lift, b - chord * (1 / 3) + lift, b),)


def _through(points: Sequence[Vec2], smooth: float = 0.5) -> tuple[Cubic, ...]:
    """A smooth curve through waypoints -- how a long edge follows the channel
    its dummy nodes reserved."""
    return catmull_rom(tuple(points), smooth, False)


def _loop(centre: Vec2, box: Rect, *, reach: float, spread: float,
          up: bool = True) -> tuple[Cubic, ...]:
    """A self-loop leaving the top (or bottom) of a box and returning to it.

    `inklet.link(x, x)` cannot do this: source and target resolve to the same
    centre, the router flags `coincident-centres`, and there is nothing to
    clip against because every ray leaves through the shape it started in.
    """
    sign = -1.0 if up else 1.0
    edge = box.y0 if up else box.y1
    left = Vec2(centre.x - spread / 2, edge)
    right = Vec2(centre.x + spread / 2, edge)
    apex = edge + sign * reach
    return (
        (left, Vec2(left.x - spread * 0.55, apex), Vec2(centre.x - spread * 0.2, apex),
         Vec2(centre.x, apex)),
        (Vec2(centre.x, apex), Vec2(centre.x + spread * 0.2, apex),
         Vec2(right.x + spread * 0.55, apex), right),
    )


def _shaft(chain: Sequence[Cubic], kind: str = "connector",
           **style) -> inklet.Diagram:
    return inklet.path(curves=chain, kind=kind, **style)


def _head(tip: Vec2, direction: Vec2, size: float, **style) -> inklet.Diagram:
    back = tip - direction * size
    side = Vec2(-direction.y, direction.x) * (size * _HEAD_HALF)
    return inklet.polygon([tip, back + side, back - side], kind="arrowhead",
                       stroke="none", **style)


def _arrow(chain: Sequence[Cubic], size: float, *, colour: str,
           width: float, kind: str = "connector") -> list[inklet.Diagram]:
    """A curved shaft plus the head it stops short of.

    Pass `kind=inklet.encoded("connector")` when the stroke width is the data;
    the weight-consistency check then reads the spread as a scale instead of
    as twenty separate design decisions.
    """
    tip = _at(chain, len(chain))
    direction = _tangent(chain, len(chain))
    return [_shaft(_shorten(chain, size * 0.92), kind,
                   stroke=colour, stroke_width=width),
            _head(tip, direction, size, fill=colour)]


# ---------------------------------------------------------------------------
# panel o -- areal hierarchy
# ---------------------------------------------------------------------------

#: Anatomical level of each area. Given, not inferred: this is the claim the
#: panel is making, and a longest-path layering would invent a different one.
#: Edges whose stroke width *is* the projection strength. Declared so the
#: weight-consistency rule reads twenty-two widths as one scale.
_ENCODED = inklet.encoded("connector")

_AREA_LEVEL = {
    "retina": 0, "LGN": 1, "V1": 2,
    "LM": 3, "RL": 3, "AL": 3, "V2": 3,
    "PM": 4, "LI": 4, "MT": 4,
    "AM": 5, "POR": 5,
}

#: Declaration order. Deliberately the order the spec lists the areas in, so
#: the naive crossing count is a number somebody could plausibly have shipped.
_AREA_ORDER = ("V1", "LM", "AL", "RL", "PM", "AM", "LI", "POR", "MT", "V2",
               "LGN", "retina")

_AREA_EDGES = (
    Edge("retina", "LGN", 1.00), Edge("LGN", "V1", 0.95),
    Edge("V1", "LM", 0.86), Edge("V1", "RL", 0.62), Edge("V1", "AL", 0.58),
    Edge("V1", "V2", 0.71),
    Edge("LM", "PM", 0.44), Edge("LM", "LI", 0.39), Edge("RL", "PM", 0.31),
    Edge("AL", "PM", 0.29), Edge("V2", "MT", 0.53),
    Edge("PM", "AM", 0.36), Edge("LI", "POR", 0.33), Edge("MT", "AM", 0.21),
    Edge("RL", "POR", 0.24), Edge("LM", "POR", 0.28),
    # Feedback. Every one of these is the return leg of an edge above, which
    # is what the curvature has to keep apart.
    Edge("LM", "V1", 0.41, "feedback"), Edge("AL", "V1", 0.24, "feedback"),
    Edge("V2", "V1", 0.33, "feedback"), Edge("V1", "LGN", 0.45, "feedback"),
    Edge("PM", "LM", 0.19, "feedback"), Edge("AM", "PM", 0.17, "feedback"),
)


def _area_node(name: str, level: int, depth: int, theme) -> inklet.Diagram:
    """A node box tinted by hierarchy level, with ink chosen to stay readable
    on whatever tint it landed on."""
    # The top of the ramp is deliberately short of `accent`: past t = 0.84 the
    # theme has no ink that clears 4.5:1 on the tint, and `text_on` answers with
    # the more readable of two unreadable choices. That ceiling is a finding.
    tint = inklet.ramp([theme.paper, theme.accent])(0.10 + 0.72 * level / depth)
    # Body size, not small: twelve two-letter labels are the entire content of
    # this panel, and a node wide enough to read is also a node wide enough to
    # fill a column without the layout resorting to airy gaps.
    return inklet.box(inklet.text(name, size=theme.font_size,
                            text_fill=theme.text_on(tint)),
                   pad=theme.gap("xs") * 1.6, radius=theme.radius * 0.8,
                   fill=tint, stroke=theme.muted,
                   stroke_width=theme.hairline).named(name)


def panel_o(width: float = 84.0, *, long_edges: str = "curve") -> inklet.Diagram:
    """Areal hierarchy as a directed weighted graph.

    Twelve areas on six anatomical levels, twenty-two edges, six of them
    reciprocal. Edge width is connection strength; feedback runs in the accent
    colour and bows the opposite way from its forward twin.

    `long_edges="avoid"` re-draws the two layer-skipping edges with
    `inklet.link(route="avoid")` instead of a curve through their dummy nodes.
    It is here because the brief asked whether the library's own router helps
    once a layout exists; render it and look before believing either answer.
    """
    if long_edges not in ("curve", "avoid"):
        raise ValueError(f"long_edges is 'curve' or 'avoid', not {long_edges!r}")
    theme = inklet.current_theme()
    depth = max(_AREA_LEVEL.values())
    nodes = {name: _area_node(name, level, depth, theme)
             for name, level in _AREA_LEVEL.items()}
    boxes = {name: node.bbox for name, node in nodes.items()}
    across = {name: box.width for name, box in boxes.items()}
    along = {name: box.height for name, box in boxes.items()}

    #: How far apart a reciprocal pair's two arcs are pushed, in mm.
    bow = theme.gap("s") * 1.15

    reciprocal = {(e.src, e.dst) for e in _AREA_EDGES
                  if (e.dst, e.src) in {(f.src, f.dst) for f in _AREA_EDGES}}
    gauge = _gauge(theme)
    key = _strength_key(theme)

    def build(cross_gap: float) -> "Layout":
        return layered(_AREA_ORDER, _AREA_LEVEL, _AREA_EDGES,
                       cross=across, flow=along, cross_gap=cross_gap,
                       flow_gap=theme.gap("m") * 0.95)

    def assemble(plan: "Layout") -> inklet.Diagram:
        # Level 0 belongs at the bottom of a hierarchy, and y grows downward.
        span = max(v.y for v in plan.pos.values())
        site = {node_: Vec2(v.x, span - v.y) for node_, v in plan.pos.items()}
        edges: list[inklet.Diagram] = []
        specs: list[object] = []
        for index, edge in enumerate(_AREA_EDGES):
            a, b = site[edge.src], site[edge.dst]
            waypoints = [site[bend] for bend in plan.bends.get(index, ())]
            if waypoints and long_edges == "avoid":
                specs.append(inklet.link(
                    nodes[edge.src], nodes[edge.dst], route="avoid",
                    arrow_size=theme.arrow_size * 0.92,
                    style=inklet.Style(stroke=theme.ink,
                                    stroke_width=gauge.map(edge.weight))))
                continue
            if waypoints:
                chain = _through([a, *waypoints, b])
            else:
                # A reciprocal pair is bowed apart by bowing *both* legs to
                # their own left. Signing them +/- looks like the obvious way
                # to separate them and is wrong: the perpendicular flips with
                # the chord, so equal-and-opposite offsets land both arcs on
                # the same side of the line and the pair overprints.
                offset = bow if (edge.src, edge.dst) in reciprocal else 0.0
                chain = _bow(a, b, offset)
            clipped = _clip(chain, _shift(boxes[edge.src], a),
                            _shift(boxes[edge.dst], b),
                            standoff=theme.gap("2xs") * 0.7)
            colour = theme.ink if edge.kind == "forward" else theme.ink_color(6)
            edges.extend(_arrow(clipped, theme.arrow_size * 0.92,
                                colour=colour, width=gauge.map(edge.weight),
                                kind=_ENCODED))

        board = inklet.place(edges
                          + [(site[name], node) for name, node in nodes.items()])
        if not specs:
            return board
        # Exactly what `Figure.link` does, minus the Figure: routing needs the
        # layout to have happened, and a panel is a Diagram, not a page.
        return inklet.Diagram(
            children=(board, inklet.route_all(specs, inklet.resolve(board))),
            kind="graph")

    # The graph gets whatever the legend beside it does not want, and the
    # overhang the arcs add beyond the outermost node is measured off a trial
    # assembly rather than estimated from `bow`.
    room = width - key.width - theme.gap("l")
    trial = build(theme.gap("m"))
    room -= assemble(trial).bbox.width - extent(trial, across)
    gap = fit_gap(lambda g: extent(build(g), across), room,
                  theme.gap("s") * 0.9, theme.gap("l") * 2.4)

    # Bottom-aligned, not centred: a hierarchy is widest at the top and the
    # legend is the only thing that will ever fill the corner under it.
    body = inklet.hstack([assemble(build(gap)), key], gap=theme.gap("l"),
                      align="bottom")
    return _titled(body, "areal hierarchy", width, theme)


def _strength_key(theme) -> inklet.Diagram:
    """The width-encodes-strength legend, built before the graph because its
    width is the graph's budget."""
    gauge = _gauge(theme)
    return inklet.legend(
        [(f"{value:.2f}", inklet.polyline([(0, 0), (5.5, 0)], kind=_ENCODED,
                                       stroke=theme.ink,
                                       stroke_width=gauge.map(value)))
         for value in (1.0, 0.5, 0.2)]
        # Not encoded: this one is a colour key, drawn at the design weight.
        + [("feedback", inklet.polyline([(0, 0), (5.5, 0)], stroke=theme.ink_color(6),
                                     stroke_width=theme.stroke))],
        title="projection strength",
    )


def _gauge(theme):
    """Connection strength -> stroke width. The linter counts the distinct
    widths this produces and calls the figure inconsistent; see the findings."""
    strengths = [e.weight for e in _AREA_EDGES]
    return inklet.linear((min(strengths), max(strengths)),
                      (theme.hairline * 1.1, theme.thick * 1.75))


def graph_crossings() -> dict[str, int]:
    """What the layout bought, for the record."""
    plan = layered(_AREA_ORDER, _AREA_LEVEL, _AREA_EDGES,
                   cross={k: 10.0 for k in _AREA_LEVEL},
                   flow={k: 5.0 for k in _AREA_LEVEL},
                   cross_gap=3.0, flow_gap=8.0)
    return {"naive": plan.naive_crossings, "barycentre": plan.crossings}


# ---------------------------------------------------------------------------
# panel p -- behavioural task state machine
# ---------------------------------------------------------------------------

_STATE_LEVEL = {"ITI": 0, "stimulus": 1, "delay": 2, "response": 3,
                "reward": 4, "timeout": 4}
_STATE_ORDER = ("ITI", "stimulus", "delay", "response", "reward", "timeout")
_STATE_TEXT = {"ITI": "ITI", "stimulus": "stimulus", "delay": "delay",
               "response": "response\nwindow", "reward": "reward",
               "timeout": "timeout"}
_TERMINAL = ("reward", "timeout")

#: The spine: the transitions the layout is allowed to see. Everything else is
#: a back edge and is drawn as an arc, which is what Sugiyama does with them.
_SPINE = (
    Edge("ITI", "stimulus"), Edge("stimulus", "delay"),
    Edge("delay", "response"), Edge("response", "reward"),
    Edge("response", "timeout"),
)


@dataclass
class _Ink:
    """The obstacle list a label has to miss: state boxes, labels already
    placed, and every drawn curve except the one being labelled.

    Sampled points stand in for the curves. inklet's router keeps an obstacle
    list of its own, but it is `Placement` bboxes and it belongs to the
    `Figure`; neither is reachable from inside a panel, and a bbox is the
    wrong shape for an arc anyway -- the bbox of the reward return covers half
    the panel while the arc itself is 0.25 mm thick.
    """

    blocked: list[Rect] = field(default_factory=list)
    strands: tuple[tuple[Vec2, ...], ...] = ()
    #: Index of the strand the label belongs to, which it is allowed to touch.
    own: int = -1

    def _crossed(self, box: Rect) -> int:
        return sum(1 for i, strand in enumerate(self.strands) if i != self.own
                   for point in strand if box.contains(point))

    def free(self, box: Rect) -> bool:
        if any(box.overlap(other) for other in self.blocked):
            return False
        return self._crossed(box) == 0

    def cost(self, box: Rect) -> float:
        covered = sum(hit.width * hit.height for hit in
                      (box.overlap(other) for other in self.blocked)
                      if hit is not None)
        # A curve under a label plate is a smaller sin than a box under it, but
        # it is still one, so it is priced rather than ignored.
        return covered + 0.25 * self._crossed(box)

    def claim(self, box: Rect) -> None:
        self.blocked.append(box)


def _state(name: str, theme) -> inklet.Diagram:
    body = inklet.box(inklet.text(_STATE_TEXT[name], size=theme.font_size_small,
                            align="center"),
                   pad=theme.gap("s") * 1.15, radius=theme.font_size * 1.1,
                   fill=theme.paper, stroke=theme.ink,
                   stroke_width=theme.stroke)
    if name not in _TERMINAL:
        return body.named(name)
    # A terminal state carries a second outline, the way an accepting state
    # does in every automaton textbook ever printed.
    return inklet.frame(body, pad=theme.gap("2xs") * 1.4,
                     radius=theme.font_size * 1.35, kind="frame").styled(
        stroke=theme.ink, stroke_width=theme.hairline * 1.4, fill="none"
    ).named(name)


def _label_on(chain: Sequence[Cubic], text: str, theme, ink: _Ink,
              *, prefer: float = 0.5, side: float = 1.0) -> inklet.Diagram | None:
    """Put a label on a curve, on whichever side of it is free.

    inklet's own link labels ride a *routed* link and are placed by the router;
    a hand-drawn curve has no router, so the candidate search is here. It is
    the same idea -- try positions, score them, take the first clear one --
    minus the router's access to the figure's obstacle list.
    """
    plate = inklet.frame(inklet.text(text, size=theme.font_size_small * 0.92),
                      pad=theme.gap("2xs") * 1.2, kind="label-plate").styled(
        fill=theme.paper, stroke="none")
    half = Vec2(plate.width / 2, plate.height / 2)
    # A full clearance step, so a plate that lands cleanly also *reads* as
    # clear: the crowding rule wants 1 mm and so does the eye at 6 pt.
    gap = theme.gap("xs") * 1.05
    total = _length(chain)
    fallback: tuple[float, Vec2] | None = None
    for share in (prefer, prefer - 0.16, prefer + 0.16, prefer - 0.3,
                  prefer + 0.3, prefer - 0.42, prefer + 0.42):
        if not 0.03 <= share <= 0.97:
            continue
        u = _param_at(chain, total * share)
        point = _at(chain, u)
        tangent = _tangent(chain, u)
        normal = Vec2(-tangent.y, tangent.x)
        reach = abs(normal.x) * half.x + abs(normal.y) * half.y
        for step in (1.0, 1.7, 2.5, 3.6, 5.0):
            for flip in (side, -side):
                centre = point + normal * (flip * (reach + gap * step))
                box = Rect(centre.x - half.x, centre.y - half.y,
                           centre.x + half.x, centre.y + half.y)
                if ink.free(box):
                    ink.claim(box)
                    return plate.translated(centre.x, centre.y)
                price = ink.cost(box)
                if fallback is None or price < fallback[0]:
                    fallback = (price, centre)
    # Never drop a label: an unlabelled transition is a wrong diagram, while a
    # label that grazes a box is a crowded one. The linter will say which.
    if fallback is None:
        return None
    centre = fallback[1]
    ink.claim(Rect(centre.x - half.x, centre.y - half.y,
                   centre.x + half.x, centre.y + half.y))
    return plate.translated(centre.x, centre.y)


def panel_p(width: float = 84.0) -> inklet.Diagram:
    """The trial as a finite-state machine.

    Self-loops, a reciprocal pair drawn as two separated arcs, and every
    transition labelled on its own curve.
    """
    theme = inklet.current_theme()
    nodes = {name: _state(name, theme) for name in _STATE_ORDER}
    boxes = {name: node.bbox for name, node in nodes.items()}
    across = {name: box.height for name, box in boxes.items()}
    along = {name: box.width for name, box in boxes.items()}

    def build(flow_gap: float) -> "Layout":
        return layered(_STATE_ORDER, _STATE_LEVEL, _SPINE,
                       cross=across, flow=along,
                       cross_gap=theme.gap("m") * 1.2, flow_gap=flow_gap)

    def assemble(plan: "Layout") -> inklet.Diagram:
        # Flow runs left to right here, so the layout's two axes swap over.
        site = {key: Vec2(v.y, v.x) for key, v in plan.pos.items()}
        world = {name: _shift(boxes[name], site[name]) for name in nodes}

        # Transitions are collected first and drawn second, because a label
        # has to dodge the curves that come after it as well as the ones
        # before it, and a one-pass loop only knows about the ones before.
        drawn: list[tuple[tuple[Cubic, ...], str, str, float, float]] = []

        def draw(chain, text, *, colour=None, prefer=0.5, side=1.0):
            drawn.append((tuple(chain), text, colour or theme.ink, prefer, side))

        def joined(a: str, b: str, *, offset: float = 0.0):
            chain = _bow(site[a], site[b], offset)
            return _clip(chain, world[a], world[b], standoff=theme.gap("2xs"))

        for a, b, text, side in (("ITI", "stimulus", "5 s", -1.0),
                                 ("stimulus", "delay", "0.5 s", -1.0),
                                 ("delay", "response", "1 s", -1.0),
                                 ("response", "reward", "lick, p = 0.8", -1.0),
                                 ("response", "timeout", "no lick", 1.0)):
            draw(joined(a, b), text, side=side)

        # An early lick during the response window sends the trial back a
        # state: a reciprocal pair, bowed the other way from `delay ->
        # response` and far enough clear that the two read as two transitions.
        draw(joined("response", "delay", offset=theme.gap("l") * 1.55),
             "early lick", colour=theme.ink_color(6), side=1.0)

        # Two states that can repeat. Neither is expressible as a inklet link.
        draw(_loop(site["ITI"], world["ITI"], reach=theme.gap("m") * 1.7,
                   spread=world["ITI"].width * 0.62),
             "lick: +2 s", side=-1.0)
        draw(_loop(site["delay"], world["delay"], reach=theme.gap("m") * 1.7,
                   spread=world["delay"].width * 0.62),
             "movement: restart", side=-1.0)

        # The returns, as arcs under everything, at three separated depths.
        # The deepest two are the reciprocal pair ITI <-> timeout. Which
        # terminal sits on top is the layout's decision, so which one has to
        # swing round the outside is read back from it rather than assumed.
        floor = max(box.y1 for box in world.values())
        clear = max(box.x1 for box in world.values()) + theme.gap("m")
        upper, lower = sorted(_TERMINAL, key=lambda name: site[name].y)
        text_of = {"reward": "3 s", "timeout": "8 s"}
        # The three arcs run parallel under the row, so labelling all three at
        # mid-arc stacks them on each other. The outer one is labelled near
        # its start instead, where it is still climbing the right-hand column
        # and has the margin to itself.
        draw(_around(world[upper], world["ITI"], floor + theme.gap("m") * 1.5,
                     clear, theme), text_of[upper], prefer=0.16, side=-1.0)
        draw(_under(world[lower], world["ITI"], floor + theme.gap("m") * 2.8,
                    theme), text_of[lower], prefer=0.04, side=1.0)
        draw(_under(world["ITI"], world["timeout"], floor + theme.gap("m") * 4.1,
                    theme),
             "lick: abort", colour=theme.ink_color(6), prefer=0.6, side=-1.0)

        ink = _Ink([world[name].pad(theme.gap("2xs")) for name in nodes],
                   strands=tuple(_strand(chain) for chain, *_ in drawn))
        edges: list[inklet.Diagram] = []
        labels: list[inklet.Diagram] = []
        for index, (chain, text, colour, prefer, side) in enumerate(drawn):
            edges.extend(_arrow(chain, theme.arrow_size, colour=colour,
                                width=theme.stroke))
            if not text:
                continue
            ink.own = index
            placed = _label_on(chain, text, theme, ink, prefer=prefer, side=side)
            if placed is not None:
                labels.append(placed)

        start = _start_marker(site["ITI"], world["ITI"], theme)
        return inklet.place(edges + start + labels
                         + [(site[name], node) for name, node in nodes.items()])

    # Strips of the panel the layout never sees -- the start marker, the column
    # the reward return swings round, the label plates hanging off the ends --
    # are measured off a trial assembly rather than guessed at. Guessing them
    # is how a panel ends up 2.5 mm over its column and gets scaled to fit,
    # taking its 6 pt type down to 5.8 pt on the way.
    trial = build(theme.gap("m"))
    margin = assemble(trial).bbox.width - extent(trial, along, "y")
    gap = fit_gap(lambda g: extent(build(g), along, "y"), width - margin,
                  theme.gap("xs") * 0.8, theme.gap("l") * 1.7)
    return _titled(assemble(build(gap)), "trial state machine", width, theme)


def _under(box_a: Rect, box_b: Rect, depth: float, theme) -> tuple[Cubic, ...]:
    """A long arc that leaves one box's underside and comes back up into
    another's, dipping to `depth`. `route="avoid"` cannot draw this: it is the
    right *path* but it comes out as three right angles, which in a state
    diagram reads as a bus rather than as a transition."""
    exit_ = Vec2(box_a.center.x, box_a.y1)
    entry = Vec2(box_b.center.x, box_b.y1)
    chain = ((exit_, Vec2(exit_.x, depth), Vec2(entry.x, depth), entry),)
    return _clip(chain, box_a, box_b, standoff=theme.gap("2xs"))


def _around(box_a: Rect, box_b: Rect, depth: float, clear: float,
            theme) -> tuple[Cubic, ...]:
    """The same return, but for a box that has another box directly beneath it.

    It leaves eastward, clears the column at `clear`, drops to `depth` and
    comes back along the bottom. Two cubics, joined at the corner, so the turn
    is a curve rather than a mitre.
    """
    exit_ = Vec2(box_a.x1, box_a.center.y)
    entry = Vec2(box_b.center.x, box_b.y1)
    chain = _through([exit_, Vec2(clear, exit_.y), Vec2(clear, depth),
                      Vec2(entry.x, depth), entry], smooth=0.42)
    return _clip(chain, box_a, box_b, standoff=theme.gap("2xs"))


def _start_marker(at: Vec2, box: Rect, theme) -> list[inklet.Diagram]:
    """The filled dot and stub arrow that says where a run begins."""
    dot = Vec2(box.x0 - theme.gap("l") * 1.15, at.y)
    chain = ((dot, dot + Vec2(2.0, 0), Vec2(box.x0 - 2.0, at.y), Vec2(box.x0, at.y)),)
    return [inklet.marker("circle", theme.font_size * 0.72,
                       fill=theme.ink).translated(dot.x, dot.y),
            *_arrow(chain, theme.arrow_size, colour=theme.ink,
                    width=theme.stroke)]


# ---------------------------------------------------------------------------
# panel r -- the multilingual caption block
# ---------------------------------------------------------------------------

CAPTION_WIDTH = 56.0


def _TAG_SIZE(theme) -> float:
    """Language tags, floored at 5 pt because that is where the linter -- and
    the printer -- stop taking type seriously."""
    return max(theme.font_size_small * 0.86, inklet.pt(5.0))


def _TAG_GUTTER(theme) -> float:
    return _TAG_SIZE(theme) * 2.0 + theme.gap("s")

_LEAD = "Fig. 1 | "
_BODY = (
    "Orientation selectivity across the mouse visual hierarchy. "
    "Two-photon calcium imaging of layer 2/3 pyramidal cells in twelve "
    "cortical areas, imaged through a chronic cranial window at 15.6 Hz. "
    "Responses are reported as the normalised fluorescence change from a "
    "pre-stimulus baseline, averaged over eight repeats of each drifting "
    "grating. Shaded bands are bootstrapped 95% confidence intervals; n = 41 "
    "mice, 9 216 cells."
)
_MATH = "ΔF/F₀ = (F − F₀)/F₀,  χ² = 4.7,  r² = 0.81"
_UNITS = "field 10⁻³ mm²,  θ = 45°,  λ = 0.04 cpd"
#: The five translated captions, each chosen to break inklet in a different way.
#: Long enough that a working line-breaker would have wrapped them, so a line
#: that comes back whole is evidence rather than a coincidence.
_TRANSLATED = (
    # Cyrillic wraps on spaces and is measured correctly. The control.
    ("ru", "зрительная кора мыши: ориентационная селективность нейронов "
           "слоя 2/3"),
    # Greek, likewise, plus the letters the maths uses.
    ("el", "θ, λ, Σ — μέγεθος δείγματος: 41 ποντίκια"),
    # No spaces anywhere. There is nothing for a greedy wrapper to break on.
    ("ja", "視覚野の方位選択性は刺激コントラストに依存する。図1cは面積ごとの"
           "選択性指数を示す。"),
    # Devanagari: reordering vowels, conjuncts, and no coverage in the body face.
    ("hi", "दृश्य प्रांतस्था में अभिविन्यास चयनात्मकता का मापन"),
    # RTL, and one embedded Latin run so the line needs real bidi, not a guess.
    ("ar", "القشرة البصرية للفأر (V1) وانتقائية الاتجاه"),
)



def _paragraph(text: str, *, width: float, size: float, theme) -> inklet.Diagram:
    """A justified paragraph, in one text node.

    This used to be forty lines of per-word placement, because `inklet.text` had
    start, center and end and no way to reach inter-word spacing. It now has
    `align="justify"`: the shaper distributes the slack into `word_spacing`
    per line, leaves the last line at its natural width, and breaks the
    paragraph with an optimal breaker rather than a greedy one. One node also
    means one box, which is what stops the crowding rule from firing on every
    adjacent pair of words -- a 0.4 mm word gap is typography, not a defect,
    but nothing in the geometry says so once each word is its own diagram.

    What is still missing is a weight argument. A Nature caption opens with a
    bold run-in ("Fig. 1 |") and there is no way to ask for one inside a run:
    `font_weight` is a style, so the renderer emits it and the browser draws
    bold text on advances measured from the regular face.
    """
    return _to_measure(
        inklet.text(text, size=size, align="justify", width=width,
                 line_height=_leading(theme, size) / size), width)


def _to_measure(block: inklet.Diagram, width: float) -> inklet.Diagram:
    """Make a block claim exactly `width`, left-aligned, however wide its ink."""
    box = block.bbox
    slack = width - box.width
    if slack <= 0:
        return block
    return inklet.pad(block, 0.0, slack, 0.0, 0.0)


def _to_width(block: inklet.Diagram, width: float) -> inklet.Diagram:
    """Claim exactly `width`: pad when the ink is narrower, scale when it is
    wider.

    Scaling is the last resort and it takes the type down with it, so it only
    fires when a panel is asked for less room than its content can physically
    hold. `inklet` has no fit-to-width of its own -- `pad`, `vstack` and `hstack`
    all size themselves from their contents -- which is why this is here.
    """
    box = block.bbox
    if box.width > width + 0.01:
        block = block.scaled(width / box.width)
        box = block.bbox
    slack = width - box.width
    return inklet.pad(block, 0.0, slack, 0.0, 0.0) if slack > 0.005 else block


def _leading(theme, size: float) -> float:
    """Baseline-to-baseline spacing that keeps two lines' *boxes* apart.

    A TextPrim's envelope is ascent + descent, which for Noto Sans is 1.362 em,
    while the theme's `line_height` is 1.25 em. Inside one prim that gap never
    shows -- a whole block is a single box -- but a paragraph set word by word
    is one box per word, and at 1.25 em every line overlaps the one above it by
    0.22 mm. The linter is right to complain; the theme token is the thing that
    is under-specified.
    """
    ink = shape("Hgy", font=theme.font_family, size=size).height
    return max(size * theme.line_height, ink * 1.02)


def _run(text: str, theme, *, size: float, width: float, lead: float,
         font: str | None = None, colour: str | None = None) -> inklet.Diagram:
    node = inklet.text(text, size=size, align="left", width=width,
                    line_height=lead / size, font=font or theme.font_family,
                    **({"text_fill": colour} if colour else {}))
    return _to_measure(node, width)


def _tagged(tag_size: float, tag: str, body: inklet.Diagram, theme) -> inklet.Diagram:
    marker = inklet.text(tag, size=tag_size, text_fill=theme.muted, align="left")
    return inklet.hstack([marker, body], gap=theme.gap("s"), align="top")


def panel_r(width: float = CAPTION_WIDTH) -> inklet.Diagram:
    """A figure caption in six scripts, in a column 56 mm wide.

    Three of the six are known failures and are here on purpose. The hairline
    rule down each side is the measure: ink crossing it is text inklet measured
    wrongly, and `caption_metrics()` says by how much.
    """
    theme = inklet.current_theme()
    size = theme.font_size_small * 0.92
    lead = _leading(theme, size)
    tag = _TAG_SIZE(theme)
    inner = width - _TAG_GUTTER(theme)   # language tags live in the left margin

    paragraph = _paragraph(_LEAD + _BODY, width=width, size=size, theme=theme)
    rule = inklet.polyline([(0, 0), (width, 0)], stroke=theme.grid,
                        stroke_width=theme.hairline)

    rows = [
        paragraph,
        _run(_MATH, theme, size=size, width=width, lead=lead),
        _run(_UNITS, theme, size=size, width=width, lead=lead),
        rule,
    ]
    for code, text in _TRANSLATED:
        rows.append(_tagged(tag, code,
                            _run(text, theme, size=size, width=inner, lead=lead),
                            theme))

    stack = inklet.vstack(rows, gap=theme.gap("s") * 1.1, align="left")
    box = stack.bbox
    measure = Rect(box.x0, box.y0 - theme.gap("s"),
                   box.x0 + width, box.y1 + theme.gap("s"))
    guides = [
        inklet.polyline([(measure.x0, measure.y0), (measure.x0, measure.y1)],
                     stroke=theme.grid, stroke_width=theme.hairline),
        inklet.polyline([(measure.x1, measure.y0), (measure.x1, measure.y1)],
                     stroke=theme.grid, stroke_width=theme.hairline),
    ]
    body = inklet.place(guides + [stack.translated(-box.center.x + (box.x0 + box.width / 2),
                                                0.0)])
    # Ink that overflows the measure must not drag the panel's box out with it,
    # or one broken line would push every neighbour across the page.
    clamped = inklet.Diagram(children=(body,), kind="caption",
                          envelope_override=Envelope.from_rect(
                              Rect(-width / 2, measure.y0, width / 2, measure.y1)))
    return _titled(clamped, "caption", width, theme)


def caption_metrics() -> dict[str, object]:
    """What inklet's text layer does to the six scripts in `panel_r`.

    Everything here is measured through the public shaper at the size the
    panel actually sets, so a composed figure can print the numbers rather
    than assert them.
    """
    theme = inklet.current_theme()
    size = theme.font_size_small * 0.92
    font = theme.font_family
    inner = CAPTION_WIDTH - _TAG_GUTTER(theme)

    out: dict[str, object] = {
        "column_mm": CAPTION_WIDTH,
        "font": font,
        "size_pt": round(size / inklet.pt(1), 2),
        "scripts": {},
    }
    samples = [("latin-math", _MATH, CAPTION_WIDTH, None),
               ("latin-units", _UNITS, CAPTION_WIDTH, None)]
    samples += [(code, text, inner, None) for code, text in _TRANSLATED]
    # What the same text costs when a font that covers it is named by hand.
    # This is the control: it separates "inklet cannot measure this" from "inklet
    # cannot break this", and it is also the only honest source for the width
    # a browser will really draw, because the SVG renderer emits the original
    # string and lets the viewer pick its own fallback font.
    covered = {code: _covered(code, text, size, inner)
               for code, text in _TRANSLATED if code in _COVERING}
    for code, text, limit, _ in samples:
        prim = shape(text, font=font, size=size, width=limit)
        cover = _coverage(text, font, size)
        real = covered.get(code)
        out["scripts"][code] = {
            "lines": len(prim.lines),
            "width_mm": round(prim.width, 3),
            "limit_mm": round(limit, 3),
            "overflow_mm": round(max(prim.width - limit, 0.0), 3),
            # What the reader actually sees, once the viewer has substituted a
            # font inklet never measured. Zero measured overflow and 31 mm of real
            # overflow is the whole failure in two numbers.
            "rendered_overflow_mm": (round(real["overflow_mm"], 3)
                                     if real else
                                     round(max(prim.width - limit, 0.0), 3)),
            "glyphs": cover["glyphs"],
            "notdef": cover["notdef"],
            "notdef_share": round(cover["notdef"] / max(cover["glyphs"], 1), 3),
            "reorders": cover["reorders"],
        }
    out["with_covering_font"] = covered
    flush = shape(_LEAD + _BODY, font=font, size=size, width=CAPTION_WIDTH,
                  align="justify")
    ragged = shape(_LEAD + _BODY, font=font, size=size, width=CAPTION_WIDTH,
                   align="start")
    stretch = [line.word_spacing for line in flush.lines]
    out["justification"] = {
        "supported_by_inklet": True,
        "lines": len(flush.lines),
        "lines_when_ragged": len(ragged.lines),
        "stretch_per_space_mm": {
            "max": round(max(stretch), 4),
            "mean": round(sum(stretch) / len(stretch), 4),
        },
        # The last line keeps its natural width, which is the one line whose
        # advance is allowed to fall short of the measure.
        "last_line_short_by_mm": round(CAPTION_WIDTH - flush.lines[-1].advance, 3),
    }
    return out


_COVERING = {"ja": "Droid Sans Fallback", "hi": "Noto Sans Devanagari",
             "ar": "Noto Sans Arabic"}


def _coverage(text: str, font: str, size: float) -> dict[str, int]:
    """Glyph ids for one run, and whether shaping reversed it.

    A .notdef here does not mean the reader sees a box: the SVG carries the
    original string and a browser will fall back to a font that has the glyph.
    It means inklet measured the wrong width, which is worse, because the layout
    is built on it and nothing downstream can tell.
    """
    from inklet.typeset.fonts import find_font
    from inklet.typeset.shaping import feature_key, shape_buffer

    if not text:
        return {"glyphs": 0, "notdef": 0, "reorders": 0}
    buffer = shape_buffer(text, find_font(font), feature_key(None))
    infos = buffer.glyph_infos
    clusters = [info.cluster for info in infos]
    backwards = sum(1 for a, b in zip(clusters, clusters[1:]) if b < a)
    return {"glyphs": len(infos),
            "notdef": sum(1 for info in infos if info.codepoint == 0),
            "reorders": backwards}


def _covered(code: str, text: str, size: float, limit: float) -> dict[str, object]:
    """The same run measured through a font that actually has the glyphs.

    This is the control: it separates "inklet cannot measure this" from "inklet
    cannot break this line", which look identical in the rendered figure.
    """
    font = _COVERING[code]
    prim = shape(text, font=font, size=size, width=limit)
    cover = _coverage(text, font, size)
    return {"font": font,
            "lines": len(prim.lines),
            "width_mm": round(prim.width, 3),
            "overflow_mm": round(max(prim.width - limit, 0.0), 3),
            "notdef": cover["notdef"],
            "reorders": cover["reorders"]}


# ---------------------------------------------------------------------------
# shared furniture
# ---------------------------------------------------------------------------


def _titled(body: inklet.Diagram, title: str, width: float, theme) -> inklet.Diagram:
    """A panel heading, and the panel padded out to its stated column width."""
    heading = inklet.text(title, size=theme.font_size_small, align="left",
                       text_fill=theme.muted)
    stack = inklet.vstack([_to_measure(heading, width), _to_width(body, width)],
                       gap=theme.gap("xs") * 1.5, align="left")
    return _to_measure(stack, width)


if __name__ == "__main__":
    import dataclasses

    inklet.use_theme(dataclasses.replace(inklet.theme("nature"), font_family="Noto Sans"))
    fig = inklet.figure(width=inklet.COLUMN_DOUBLE)
    fig.add(inklet.vstack([
        inklet.hstack([panel_o(84.0), panel_r(CAPTION_WIDTH)],
                   gap=10, align="top"),
        panel_p(84.0),
    ], gap=12, align="left"))
    fig.save("stress/panels/graphs.svg")
    print(fig.report())
    print("layout cost:", layout_cost())
    print("crossings:", graph_crossings())
