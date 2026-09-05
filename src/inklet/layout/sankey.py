"""`inklet.sankey()` -- a flow diagram whose ribbons are as wide as what they carry.

A Sankey is the one drawing where the *thickness* of a line is the datum, and
that changes what a layout has to get right. A node-link graph may put its
boxes anywhere legible, because the arrows only say *that* A feeds B. Here the
bar's height **is** a total, the ribbons leaving it tile its face with no gap
and no overlap, and the reader takes the proportions straight off the page. So
three things decide whether the picture is honest, and they are what this
module does.

**Height is throughput.** Every node is a bar `max(inflow, outflow)` tall at
one shared scale, and the scale is the one that makes the busiest column fill
the height it was given. Nothing is normalised per column: two bars the same
height anywhere on the page stand for the same quantity, which is the only
reading a Sankey supports.

**Order within a column is a crossing-minimisation problem**, and a stated,
deterministic one. Nodes start in the order the flows first mention them, then
`sweeps` barycentre passes run forward and backward across the ranks, and the
best arrangement any pass produced is polished by adjacent swaps while a swap
strictly helps. Ties break on the incoming order, every pass is scored by the
same counter, and the answer is a pure function of the input -- no force
field, no restarts, no seed. `order="given"` turns the whole thing off, which
is how the improvement gets measured rather than asserted (`crossings`).

**The attachment is where a Sankey looks amateur or does not.** Three rules,
and all three are about the node face:

* Ribbons stack contiguously. Each face is walked once with a running sum, so
  band *k* ends at exactly the float band *k+1* starts at: adjacent bands
  share an edge value rather than nearly sharing one, and no arithmetic can
  open a hairline between them.
* The stack is ordered by where the far end sits, so the bands leaving one bar
  fan out in the same order they arrive in, and two ribbons out of one node
  never cross each other in the first millimetre.
* Ribbons run from bar *centre* to bar *centre* and the bars are painted last.
  The end of every band is therefore under an opaque rectangle, and the
  attachment the reader sees is the bar's own edge -- one straight line, no
  seam between the band and the node, and nothing to misregister when a viewer
  rounds coordinates to device pixels.

The band itself is `inklet.ribbon_between`: one closed contour of four cubics,
both long edges eased along the same flow direction so every cross-section is
square to the flow. That already existed for hand-built flows; this module is
the layout above it, not a second copy of it.

    fates = inklet.sankey([("progenitor", "neuron", 40),
                        ("progenitor", "glia", 22)])
    fig.add(fates.diagram)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping, Sequence

from ..core import Diagram, DiagramError, Rect, RectPrim, Vec2, mm

__all__ = [
    "DIRECTIONS", "ORDERS", "Sankey", "SankeyError", "SankeyFlow",
    "SankeyNode", "SANKEY_KIND", "TINTS", "sankey",
]

Length = float | int | str

SANKEY_KIND = "sankey"

#: The bar. Deliberately not a `box`: a Sankey node has no text inside it and
#: its height is data, so the theme's box role would be styling a measurement.
NODE_KIND = "sankey-node"

#: Which end of a flow gives a ribbon its colour. `"source"` lets a reader
#: follow one cohort forward out of the bar it came from, which is what a
#: Sankey is usually for; `"target"` reads the same picture backwards, and is
#: the right choice for a first column that is one undifferentiated pool --
#: there, colouring by source paints every band the same grey.
TINTS = ("source", "target")

#: How the order within a column is decided. `"given"` is the control case --
#: first mention wins -- and exists so the barycentre pass can be measured.
ORDERS = ("barycentre", "given")

#: Which way the flow runs. A Sankey is drawn along one axis and stacked
#: across it; the other two compass directions are the same two pictures
#: mirrored, and nobody publishes them.
DIRECTIONS = ("right", "down")

#: Barycentre sweeps are cheap and stop helping quickly; the polish pass after
#: them is where the last crossings go. Four matches `inklet.graph`'s layered
#: default, for the same reason: it is past the knee on every corpus figure.
DEFAULT_SWEEPS = 4

#: Passes of the position relaxation. Ordering decides *who* is above whom;
#: this decides *where*, by pulling each bar towards the value-weighted mean
#: of what it connects to, then re-separating the column. Six is d3-sankey's
#: number and the point past which bars stop visibly moving.
DEFAULT_RELAX = 6

#: Descent-then-sidestep rounds in the adjacent-swap polish. Two is where it
#: stops finding anything on every fixture here; the cost of a round is one
#: trial layout per adjacent pair, which is cheap next to shaping the labels.
_TRANSPOSE_ROUNDS = 2

#: Each relaxation pass moves a bar this fraction of the way to its target,
#: decaying per pass so the sequence converges instead of ringing.
_RELAX_ALPHA = 0.9

_EPS = 1e-9


class SankeyError(DiagramError):
    """A flow diagram that cannot be laid out as asked."""


@dataclass(frozen=True)
class SankeyNode:
    """One bar: what it is, where the layout put it, and how much goes through.

    `box` is in the frame the ribbons and bars were drawn in, which is the
    frame *inside* the returned diagram's own centring transform -- the same
    arrangement `inklet.graph` returns, and the reason `diagram` rather than
    `box` is what you hand to `fig.link` or `inklet.annotate`.
    """

    key: object
    label: str
    rank: int
    order: int
    value: float
    box: Rect
    diagram: Diagram


@dataclass(frozen=True)
class SankeyFlow:
    """One ribbon, resolved: its two nodes, its value, and the band drawn."""

    source: SankeyNode
    target: SankeyNode
    value: float
    diagram: Diagram


@dataclass(frozen=True)
class Sankey:
    """What `inklet.sankey()` returns: the drawing, and everything it decided.

    `diagram` is an ordinary `Diagram` -- stack it, pad it, frame it, put it in
    a panel. The rest is the layout showing its work: `crossings` is how many
    pairs of ribbons cross, `unit` is the millimetres one unit of value came
    out as, and `nodes`/`flows` carry the geometry each piece was given.
    """

    diagram: Diagram
    nodes: tuple[SankeyNode, ...]
    flows: tuple[SankeyFlow, ...]
    crossings: int
    unit: float
    keys: Mapping[object, int] = field(default_factory=dict)

    def add_to(self, figure) -> Diagram:
        """Put the drawing on a figure. Nothing to route: a ribbon is content."""
        figure.add(self.diagram)
        return self.diagram

    def __getitem__(self, key) -> Diagram:
        """A node's bar, by key or by index -- what an annotation aims at."""
        if isinstance(key, int) and key not in self.keys:
            return self.nodes[key].diagram
        index = self.keys.get(key)
        if index is None:
            raise KeyError(key)
        return self.nodes[index].diagram

    def node(self, key) -> SankeyNode:
        """The full record for a node, rank and value included."""
        index = self.keys.get(key)
        if index is None:
            raise KeyError(key)
        return self.nodes[index]

    @property
    def bbox(self) -> Rect:
        return self.diagram.bbox

    @property
    def width(self) -> float:
        return self.diagram.width

    @property
    def height(self) -> float:
        return self.diagram.height


def sankey(flows: Iterable[Sequence], *, nodes: Iterable = (),
           labels: Mapping | Callable[[object], str] | None = None,
           length: Length | None = None, breadth: Length | None = None,
           node_width: Length | None = None, gap: Length | None = None,
           label_gap: Length | None = None, direction: str = "right",
           order: str = "barycentre", sweeps: int = DEFAULT_SWEEPS,
           relax: int = DEFAULT_RELAX, ease: float | None = None,
           color: Mapping | Callable[[object], str] | None = None,
           tint: str = "source", opacity: float = 0.55,
           halo: float | None = None, name: str | None = None) -> Sankey:
    """Lay out a Sankey from its flows and draw it.

    `flows` is a sequence of `(source, target, value)`. The keys are yours --
    strings read best -- and the nodes are the keys the flows mention, in the
    order they first mention them. `nodes` names extra keys, or fixes that
    order when you want `order="given"` to mean something specific.

    `length` is how far the whole drawing runs along the flow -- **names
    included**, so `length=inklet.COLUMN_SINGLE` produces something that fits a
    single column rather than something whose end labels hang off the page.
    `breadth` is how far the bars stack across it, and the value scale falls
    out of it rather than being set directly, because a figure has a column to
    fit and a Sankey has no natural size. A name above an interior bar
    overhangs `breadth`; the two ends are the only sides that can be reserved
    for in advance. `node_width`, `gap` (clear space between two bars in a
    column) and `label_gap` default to the theme's spacing scale.

    `direction` is `"right"` or `"down"`. `order` is `"barycentre"`, the
    crossing-minimising pass described in the module docstring, or `"given"`
    to keep the order the keys arrived in. `relax` is how many passes
    straighten the bars afterwards without reordering them.

    `labels` is a mapping or a function from key to text, `False` for none;
    leave it out and the keys are used. `color` is the same for fills: each
    node's bar takes its colour, and each ribbon takes its *source's* at
    `opacity`, which is the convention that lets a reader follow one cohort
    across the page. Without one, the theme's categorical palette is used in
    node order. `tint` says which end a ribbon takes its colour from:
    `"source"` by default, or `"target"` where the first column is one
    undifferentiated pool and colouring by source would paint every band the
    same grey.

    Handles survive: `sk["progenitor"]` is the bar itself, so an annotation or
    a bracket can be aimed at it after the fact. `annotate` returns the target's
    whole tree with the callout added, so the annotated drawing is what goes on
    the figure -- adding `sk.diagram` as well would place it twice::

        sk = inklet.sankey(FLOWS, labels=NAMES, breadth=48)
        fig.add(inklet.annotate(sk["neuron"], "70% of the cohort", side="e",
                             within=sk.diagram))
    """
    if order not in ORDERS:
        raise SankeyError(
            f"unknown sankey order {order!r}; use one of {', '.join(ORDERS)}")
    if direction not in DIRECTIONS:
        raise SankeyError(
            f"unknown sankey direction {direction!r}; "
            f"use one of {', '.join(DIRECTIONS)}")
    if sweeps < 0 or relax < 0:
        raise SankeyError(f"sweeps and relax cannot be negative, got {sweeps} and {relax}")
    if tint not in TINTS:
        raise SankeyError(
            f"unknown sankey tint {tint!r}; use one of {', '.join(TINTS)}")
    if not 0.0 < opacity <= 1.0:
        raise SankeyError(f"opacity must be in (0, 1], got {opacity}")

    keys, edges = _read(flows, nodes)
    ranks = _ranks(len(keys), edges)
    values = _values(len(keys), edges)
    metrics = _Metrics(len(keys), edges, ranks, values)

    # Names are shaped before anything is placed, because the two end columns'
    # names are the part of the drawing that sticks out past the bars and
    # `length` is measured over the lot. Nothing about a name depends on where
    # the layout puts its bar, so this costs one pass and buys a figure that
    # fits the column it was asked for.
    names = _names(keys, labels, halo)
    sizes = _sizes(length, breadth, node_width, gap, label_gap,
                   names, ranks, direction)
    columns = _columns(ranks)
    if order == "barycentre":
        columns = _minimise(columns, metrics, sizes, sweeps, relax)
    placed = _places(columns, metrics, sizes, relax)
    faces = _faces(placed, metrics)
    return _draw(keys, metrics, placed, faces, sizes, columns, direction,
                 names, color, tint, opacity, ease, name)


# -- reading the flows ----------------------------------------------------


def _read(flows: Iterable[Sequence], nodes: Iterable
          ) -> tuple[list[object], list[tuple[int, int, float]]]:
    """Keys in first-mention order, and the flows as index triples.

    Order matters twice over: it is the starting arrangement the barycentre
    pass improves on, and it is `order="given"` in full. So it is taken from
    the input rather than from a sort, and `nodes=` is how an author states it
    instead of relying on the shape of their flow list.
    """
    keys: list[object] = []
    index: dict[object, int] = {}

    def slot(key: object, where: str) -> int:
        try:
            found = index.get(key)
        except TypeError:
            raise SankeyError(
                f"sankey {where} {key!r} is not hashable, so it cannot name a node"
            ) from None
        if found is None:
            found = index[key] = len(keys)
            keys.append(key)
        return found

    for key in nodes:
        slot(key, "node")

    edges: list[tuple[int, int, float]] = []
    seen: dict[tuple[int, int], int] = {}
    for position, spec in enumerate(flows):
        try:
            source, target, value = spec
        except (TypeError, ValueError):
            raise SankeyError(
                f"flow {position} is {spec!r}; a flow is (source, target, value)"
            ) from None
        amount = float(value)
        if not amount > 0.0:
            raise SankeyError(
                f"flow {position} ({source!r} -> {target!r}) carries {value!r}; "
                "a ribbon's width is its value, so it has to be positive"
            )
        u, v = slot(source, "source"), slot(target, "target")
        if u == v:
            raise SankeyError(
                f"flow {position} runs {source!r} -> {source!r}; a Sankey node "
                "cannot feed itself, since the two ends would share a face"
            )
        if (u, v) in seen:
            raise SankeyError(
                f"flow {position} repeats {source!r} -> {target!r}, already "
                f"given as flow {seen[(u, v)]}; add the values up instead -- "
                "two bands between one pair of bars read as two different routes"
            )
        seen[(u, v)] = position
        edges.append((u, v, amount))
    if not edges:
        raise SankeyError("a sankey needs at least one flow")
    return keys, edges


def _ranks(count: int, edges: Sequence[tuple[int, int, float]]) -> list[int]:
    """Longest path from a source, which is the column each node belongs in.

    Longest rather than shortest: a flow must never point backwards, and a node
    fed by both a rank-0 and a rank-2 node has to sit past *both* of them.
    Kahn's algorithm, so a cycle names itself rather than looping.
    """
    incoming = [0] * count
    after: list[list[int]] = [[] for _ in range(count)]
    for u, v, _ in edges:
        after[u].append(v)
        incoming[v] += 1
    rank = [0] * count
    queue = [i for i in range(count) if incoming[i] == 0]
    settled = 0
    while queue:
        node = queue.pop(0)
        settled += 1
        for nxt in after[node]:
            rank[nxt] = max(rank[nxt], rank[node] + 1)
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                queue.append(nxt)
    if settled != count:
        stuck = [i for i in range(count) if incoming[i] > 0]
        raise SankeyError(
            f"the flows form a cycle through {len(stuck)} node(s); a Sankey is "
            "read left to right, so every flow has to point forward"
        )
    return rank


def _values(count: int, edges: Sequence[tuple[int, int, float]]) -> list[float]:
    """A node's throughput: the larger of what reaches it and what leaves.

    Not the sum of both, which would double every interior bar, and not one
    side alone, which would draw a leaky node too small to hold its own
    ribbons.
    """
    into = [0.0] * count
    out = [0.0] * count
    for u, v, value in edges:
        out[u] += value
        into[v] += value
    return [max(a, b) for a, b in zip(into, out)]


@dataclass(frozen=True)
class _Metrics:
    """The graph as the layout passes want it: neighbours, both ways, by index."""

    count: int
    edges: tuple[tuple[int, int, float], ...]
    ranks: tuple[int, ...]
    values: tuple[float, ...]
    out_of: tuple[tuple[int, ...], ...]
    into: tuple[tuple[int, ...], ...]

    def __init__(self, count, edges, ranks, values):
        out_of: list[list[int]] = [[] for _ in range(count)]
        into: list[list[int]] = [[] for _ in range(count)]
        for position, (u, v, _) in enumerate(edges):
            out_of[u].append(position)
            into[v].append(position)
        object.__setattr__(self, "count", count)
        object.__setattr__(self, "edges", tuple(edges))
        object.__setattr__(self, "ranks", tuple(ranks))
        object.__setattr__(self, "values", tuple(values))
        object.__setattr__(self, "out_of", tuple(tuple(e) for e in out_of))
        object.__setattr__(self, "into", tuple(tuple(e) for e in into))


@dataclass(frozen=True)
class _Sizes:
    """Every millimetre the drawing is built from, resolved once."""

    length: float
    breadth: float
    node: float
    gap: float
    label_gap: float


def _sizes(length, breadth, node_width, gap, label_gap,
           names: Sequence["_Name"], ranks: Sequence[int],
           direction: str) -> _Sizes:
    """Theme spacing unless told otherwise, exactly as `inklet.graph` does it.

    The one thing that is not a token: `length` arrives as the extent of the
    finished drawing and leaves as the run between the outer *bars*, with the
    end columns' names taken off it. That subtraction is why a default-sized
    Sankey fits its column instead of pushing four names over the edge.
    """
    from .. import COLUMN_SINGLE, current_theme   # late: inklet imports layout, not back

    theme = current_theme()
    run = COLUMN_SINGLE if length is None else mm(length)
    # A landscape default, because a Sankey is read along its flow and a tall
    # one crowds every name against its neighbour. Overridden by `breadth`.
    across = run * 0.6 if breadth is None else mm(breadth)
    node = theme.gap("s") if node_width is None else mm(node_width)
    pad = theme.gap("xs") if label_gap is None else mm(label_gap)
    reserved = _reserved(names, ranks, direction, pad)
    # The clear space between two bars is also the space a name has to live
    # in, so the default is the theme's until a name needs more. That is what
    # makes the whole arrangement safe by construction: an interior name sits
    # in the gap above its bar, and a gap at least one name deep means no name
    # can reach the bar above it or the name beside it. An explicit `gap=`
    # is taken as given -- an author asking for a tight column has decided.
    room = max((_across_of(name.block, direction) for name in names
                if name.block is not None), default=0.0)
    sizes = _Sizes(
        length=run - reserved, breadth=across, node=node,
        gap=(max(theme.gap("m"), room + pad) if gap is None else mm(gap)),
        label_gap=pad)
    for label, value in (("breadth", sizes.breadth), ("node_width", sizes.node)):
        if value <= 0.0:
            raise SankeyError(f"sankey {label} must be positive, got {value}")
    if sizes.length <= sizes.node:
        raise SankeyError(
            f"the end labels need {reserved:.3g}mm of the {run:.3g}mm asked "
            f"for, leaving no room for the flow; raise length= or pass "
            "labels=False"
        )
    for label, value in (("gap", sizes.gap), ("label_gap", sizes.label_gap)):
        if value < 0.0:
            raise SankeyError(f"sankey {label} cannot be negative, got {value}")
    return sizes


def _reserved(names: Sequence["_Name"], ranks: Sequence[int], direction: str,
              label_gap: float) -> float:
    """Millimetres the first and last columns' names take off the flow's run.

    Only those two: every other name sits across the flow, where nothing can
    be reserved for it without making the value scale depend on how long
    somebody's node names are.
    """
    last = max(ranks, default=0)
    if last == 0:
        return 0.0
    ends = [0.0, 0.0]
    for name, rank in zip(names, ranks):
        if name.block is None or rank not in (0, last):
            continue
        size = name.block.width if direction == "right" else name.block.height
        side = 0 if rank == 0 else 1
        ends[side] = max(ends[side], size + label_gap)
    return ends[0] + ends[1]


def _across_of(block: Diagram, direction: str) -> float:
    """How much of the stacking axis one name takes."""
    return block.height if direction == "right" else block.width


# -- ordering -------------------------------------------------------------


def _columns(ranks: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    """Node indices per rank, in first-mention order -- the starting layout."""
    out: list[list[int]] = [[] for _ in range(max(ranks) + 1)]
    for index, rank in enumerate(ranks):
        out[rank].append(index)
    return tuple(tuple(column) for column in out)


def _minimise(columns, metrics: _Metrics, sizes: _Sizes, sweeps: int,
              relax: int) -> tuple[tuple[int, ...], ...]:
    """Barycentre sweeps, then adjacent swaps, scored by ribbons that cross.

    The score is geometric rather than combinatorial -- lay the arrangement
    out and count the pairs of ribbon centre lines that actually intersect --
    for two reasons. It is the number the reader sees, which a per-layer
    inversion count is only a proxy for; and it is defined for a flow that
    skips a rank, where an inversion count between adjacent layers has nothing
    to say. Laying out a candidate is a hundred microseconds at figure sizes,
    so honesty is affordable here.

    Every pass is *offered*, never imposed: an arrangement is kept only if it
    scores strictly better than the best so far, so a barycentre sweep can
    never make the drawing worse than the order the author typed.
    """
    best = columns
    score = _score(columns, metrics, sizes, relax)
    current = columns
    for sweep in range(sweeps):
        for forward in (True, False):
            current = _barycentre(current, metrics, forward)
            here = _score(current, metrics, sizes, relax)
            if here < score:
                best, score = current, here
        if score == 0:
            break
    return _transpose(best, metrics, sizes, relax, score)[0]


def _barycentre(columns, metrics: _Metrics, forward: bool
                ) -> tuple[tuple[int, ...], ...]:
    """Each node moved to the mean position of the neighbours on one side.

    Positions are slot indices, not millimetres, and the mean is unweighted:
    the objective this feeds is a crossing count, and a crossing costs the
    same whichever ribbon carries more. Value-weighting belongs in the
    relaxation, where the question is which bars to straighten.

    A node with no neighbour on the side being swept keeps its own slot, so it
    drifts with the column instead of collapsing to the top of it. The sort is
    stable, so equal barycentres keep the order they came in with.
    """
    place = {node: slot for column in columns for slot, node in enumerate(column)}
    out = list(columns)
    order = range(1, len(columns)) if forward else range(len(columns) - 2, -1, -1)
    for rank in order:
        column = out[rank]
        keyed = []
        for slot, node in enumerate(column):
            sides = metrics.into[node] if forward else metrics.out_of[node]
            others = [metrics.edges[e][0] if forward else metrics.edges[e][1]
                      for e in sides]
            centre = (sum(place[o] for o in others) / len(others)
                      if others else float(slot))
            keyed.append((centre, slot, node))
        keyed.sort(key=lambda item: (item[0], item[1]))
        out[rank] = tuple(node for _, _, node in keyed)
        for slot, node in enumerate(out[rank]):
            place[node] = slot
    return tuple(out)


def _transpose(columns, metrics: _Metrics, sizes: _Sizes, relax: int,
               score: int) -> tuple[tuple[tuple[int, ...], ...], int]:
    """Swap adjacent pairs while a swap strictly helps, top to bottom.

    The classic Sugiyama polish, and the reason the barycentre passes can stop
    early: a sweep gets the column roughly right and leaves a handful of
    neighbouring pairs the wrong way round. Strictly helps, so it terminates;
    top to bottom over ranks in order, so it terminates *the same way* twice.
    A strict descent sometimes stalls one swap short, because the node that
    wants to move two slots has to pass through a position costing exactly
    what its own costs now. So each descent is followed by one *sidestep*
    pass that accepts an equal score as well, and the whole thing repeats
    `_TRANSPOSE_ROUNDS` times. The best arrangement ever seen is what comes
    back, so a sidestep can only find something or waste a pass: over 25
    random four-rank fixtures it improved three and worsened none, and in
    each of the three it landed exactly on the brute-force optimum.

    It is a greedy, and greedies leave crossings on the table. On
    `stress/flow.py` this one settles at eleven where an exhaustive search of
    all 2880 arrangements finds ten -- the two orders are three adjacent swaps
    apart across two columns, and every one-swap neighbourhood in between
    costs more, so no descent and no plateau walk connects them.
    Buying that last crossing costs an exponential search; the arrangement is
    reported as `Sankey.crossings` so an author who wants it can pin the
    order by hand and see the number fall.
    """
    best, cost = columns, score
    current, here = columns, score
    for _ in range(_TRANSPOSE_ROUNDS):
        current, here = _descend(current, here, metrics, sizes, relax)
        if here < cost:
            best, cost = current, here
        if cost == 0:
            break
        current, here = _sidestep(current, here, metrics, sizes, relax)
    return best, cost


def _descend(columns, score: int, metrics: _Metrics, sizes: _Sizes, relax: int
             ) -> tuple[tuple[tuple[int, ...], ...], int]:
    """Adjacent swaps while one strictly helps. Terminates: the score falls."""
    improved = True
    # Each accepted swap removes at least one crossing, so the loop is bounded
    # by the score it started with; the +1 lets it confirm nothing helps.
    for _ in range(score + 1):
        if not improved:
            break
        improved = False
        for rank, column in enumerate(columns):
            for slot in range(len(column) - 1):
                trial = _swapped(columns, rank, slot)
                here = _score(trial, metrics, sizes, relax)
                if here < score:
                    columns, score, improved = trial, here, True
    return columns, score


def _sidestep(columns, score: int, metrics: _Metrics, sizes: _Sizes,
              relax: int) -> tuple[tuple[tuple[int, ...], ...], int]:
    """One pass that also takes a swap costing exactly what it costs now.

    Exactly one pass, each pair offered once, so it cannot oscillate: the
    caller's strict descent then either finds something from where this landed
    or does not, and either way the best arrangement seen is kept.
    """
    for rank, column in enumerate(columns):
        for slot in range(len(column) - 1):
            trial = _swapped(columns, rank, slot)
            here = _score(trial, metrics, sizes, relax)
            if here <= score:
                columns, score = trial, here
    return columns, score


def _swapped(columns, rank: int, slot: int) -> tuple[tuple[int, ...], ...]:
    out = list(columns)
    column = list(out[rank])
    column[slot], column[slot + 1] = column[slot + 1], column[slot]
    out[rank] = tuple(column)
    return tuple(out)


def _score(columns, metrics: _Metrics, sizes: _Sizes, relax: int) -> int:
    """Ribbons that cross, for one candidate arrangement."""
    placed = _places(columns, metrics, sizes, relax)
    return _crossings(_centre_lines(placed, metrics, _faces(placed, metrics)))


def _crossings(lines: Sequence[tuple[Vec2, Vec2]]) -> int:
    """Pairs of ribbons whose centre lines properly cross.

    Centre lines rather than outlines: two bands leaving one bar touch along
    their whole first millimetre and a contour test would call that a
    crossing, when it is the fan every Sankey draws. Properly, too -- shared
    endpoints and collinear overlaps do not count, so a flow passing exactly
    through a bar it does not touch is not double-counted against its
    neighbours.
    """
    total = 0
    for i in range(len(lines)):
        p0, p1 = lines[i]
        for j in range(i + 1, len(lines)):
            q0, q1 = lines[j]
            if _crosses(p0, p1, q0, q1):
                total += 1
    return total


def _crosses(p0: Vec2, p1: Vec2, q0: Vec2, q1: Vec2) -> bool:
    a, b = _side(p0, p1, q0), _side(p0, p1, q1)
    c, d = _side(q0, q1, p0), _side(q0, q1, p1)
    return a * b < 0.0 and c * d < 0.0


def _side(a: Vec2, b: Vec2, p: Vec2) -> float:
    value = (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x)
    return 0.0 if abs(value) <= _EPS else value




# -- positions ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Placed:
    """One arrangement, measured. Canonical frame: `along` the flow, `across` it.

    `across` is where a bar *starts*; it plus `height` is where it ends. Two
    arrays rather than a rect per node because the relaxation rewrites one of
    them in place a few hundred times and nothing else about a bar moves.
    """

    unit: float
    along: tuple[float, ...]
    across: tuple[float, ...]
    height: tuple[float, ...]


def _places(columns, metrics: _Metrics, sizes: _Sizes, relax: int) -> _Placed:
    """Lay one arrangement out: column centres, bar starts, bar heights."""
    unit = _unit(columns, metrics, sizes)
    heights = [value * unit for value in metrics.values]
    ranks = len(columns)
    pitch = 0.0 if ranks < 2 else (sizes.length - sizes.node) / (ranks - 1)
    start = -(sizes.length - sizes.node) / 2.0

    across = [0.0] * metrics.count
    for column in columns:
        total = sum(heights[n] for n in column) + sizes.gap * (len(column) - 1)
        cursor = -total / 2.0
        for node in column:
            across[node] = cursor
            cursor += heights[node] + sizes.gap
    _relax(columns, metrics, heights, across, sizes, relax)

    return _Placed(
        unit=unit,
        along=tuple(start + pitch * metrics.ranks[n] for n in range(metrics.count)),
        across=tuple(across),
        height=tuple(heights),
    )


def _unit(columns, metrics: _Metrics, sizes: _Sizes) -> float:
    """Millimetres per unit of value: whatever makes the tightest column fit.

    Per drawing, never per column. A Sankey whose scale changed between ranks
    would draw one number at two heights, and the entire reading of the
    diagram is that it does not.
    """
    best = None
    for column in columns:
        total = sum(metrics.values[n] for n in column)
        room = sizes.breadth - sizes.gap * (len(column) - 1)
        if room <= 0.0:
            raise SankeyError(
                f"a column of {len(column)} bars needs more than "
                f"{sizes.breadth:.3g}mm of breadth at gap={sizes.gap:.3g}mm; "
                "raise breadth= or lower gap="
            )
        if total > 0.0:
            here = room / total
            best = here if best is None else min(best, here)
    if best is None or best <= 0.0:      # pragma: no cover - _read rejects this
        raise SankeyError("every flow carries zero, so nothing has a width")
    return best


def _relax(columns, metrics: _Metrics, heights: Sequence[float],
           across: list[float], sizes: _Sizes, passes: int) -> None:
    """Pull each bar towards what it connects to, without reordering anything.

    Ordering has already settled who is above whom; this settles where in the
    column they sit, and it is what turns a stack of centred columns into a
    drawing whose big ribbons run flat. The target is the value-weighted mean
    of the neighbours' centres -- weighted here, unlike the barycentre pass,
    because the question has changed: not "which order has fewest crossings"
    but "which ribbons are worth straightening", and a thick one is worth
    more than a thin one.

    `_separate` runs after every pass and walks the column in its *given*
    order, so a bar can never overtake its neighbour. The arrangement the
    ordering pass scored is the arrangement the drawing has.
    """
    if not passes:
        return
    limit = sizes.breadth / 2.0
    for step in range(passes):
        alpha = _RELAX_ALPHA ** step
        for forward in (True, False):
            order = (range(1, len(columns)) if forward
                     else range(len(columns) - 2, -1, -1))
            for rank in order:
                for node in columns[rank]:
                    edges = metrics.into[node] if forward else metrics.out_of[node]
                    weight = sum(metrics.edges[e][2] for e in edges)
                    if weight <= 0.0:
                        continue
                    far = 0 if forward else 1
                    target = sum(
                        metrics.edges[e][2] * (across[metrics.edges[e][far]]
                                               + heights[metrics.edges[e][far]] / 2.0)
                        for e in edges) / weight
                    centre = across[node] + heights[node] / 2.0
                    across[node] += (target - centre) * alpha
                _separate(columns[rank], heights, across, sizes.gap, limit)


def _separate(column: Sequence[int], heights: Sequence[float],
              across: list[float], gap: float, limit: float) -> None:
    """Push the column apart in its own order, then back inside the bounds."""
    cursor = -limit
    for node in column:
        if across[node] < cursor:
            across[node] = cursor
        cursor = across[node] + heights[node] + gap
    if cursor - gap > limit:
        cursor = limit
        for node in reversed(column):
            cursor -= heights[node]
            if across[node] > cursor:
                across[node] = cursor
            cursor -= gap


# -- faces ----------------------------------------------------------------


def _faces(placed: _Placed, metrics: _Metrics
           ) -> tuple[tuple[float, float, float, float], ...]:
    """Where each flow meets its two bars: `(from_lo, from_hi, to_lo, to_hi)`.

    The stacking order is decided here and nowhere else: a node's ribbons are
    sorted by where their far end sits, so bands leaving one bar arrive in the
    order they left and no pair of them crosses in its first millimetre. Ties
    break on the flow's position in the input, which is what stops two flows
    to bars of equal height from swapping between runs.

    Each face is walked once with a running cursor, so consecutive bands share
    an edge coordinate exactly instead of to within a rounding -- there is no
    arithmetic left that could open a hairline between two neighbours. The
    stack is centred on the bar, which matters only where a node leaks: the
    bar is as tall as its larger side, and the smaller side then sits in the
    middle of it rather than hanging off the top.
    """
    span = [[0.0, 0.0, 0.0, 0.0] for _ in metrics.edges]
    for node in range(metrics.count):
        for outgoing in (True, False):
            edges = metrics.out_of[node] if outgoing else metrics.into[node]
            if not edges:
                continue
            far = 1 if outgoing else 0
            ordered = sorted(edges, key=lambda e: (
                placed.across[metrics.edges[e][far]]
                + placed.height[metrics.edges[e][far]] / 2.0,
                placed.along[metrics.edges[e][far]], e))
            total = sum(metrics.edges[e][2] for e in ordered) * placed.unit
            cursor = placed.across[node] + (placed.height[node] - total) / 2.0
            for edge in ordered:
                width = metrics.edges[edge][2] * placed.unit
                slot = 0 if outgoing else 2
                span[edge][slot] = cursor
                cursor += width
                span[edge][slot + 1] = cursor
    return tuple((a, b, c, d) for a, b, c, d in span)


def _centre_lines(placed: _Placed, metrics: _Metrics,
                  faces: Sequence[tuple[float, float, float, float]]
                  ) -> tuple[tuple[Vec2, Vec2], ...]:
    return tuple(
        (Vec2(placed.along[u], (lo0 + hi0) / 2.0),
         Vec2(placed.along[v], (lo1 + hi1) / 2.0))
        for (u, v, _), (lo0, hi0, lo1, hi1) in zip(metrics.edges, faces)
    )


# -- names ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Name:
    """A node's name, already shaped. `block` is None when it has none."""

    text: str
    block: Diagram | None


def _names(keys: Sequence, labels, halo: float | None) -> tuple[_Name, ...]:
    """Shape every node name once, in the theme in force.

    The halo is paper painted under the glyphs, and it is the default here
    rather than an option an author has to find: an interior name sits over
    the ribbons its own bar sends out, and a halo is what keeps its counters
    open without a plate blanking the picture behind them. `halo=0` turns it
    off for a drawing sparse enough not to need it.
    """
    from .. import current_theme, label as make_label   # late; see `_sizes`

    width = current_theme().stroke * 2.0 if halo is None else float(halo)
    if width < 0.0:
        raise SankeyError(f"halo cannot be negative, got {halo}")
    out = []
    for key in keys:
        text = "" if labels is False else _text_of(labels, key)
        block = None if not text else (
            make_label(text, halo=width) if width > 0.0 else make_label(text))
        out.append(_Name(text=text, block=block))
    return tuple(out)


def _text_of(labels, key) -> str:
    if labels is None or labels is True:
        return str(key)
    if isinstance(labels, Mapping):
        return str(labels.get(key, key))
    return str(labels(key))


# -- drawing --------------------------------------------------------------

#: Where a name sits relative to its bar, and the anchor that puts it there.
#: The first column reads back out of the drawing and the last one forward out
#: of it, which is the only room either end has. Everything between goes to the
#: across-negative side -- above the bar in a rightward drawing, beside it in a
#: downward one -- because the room ahead of an interior bar is exactly where
#: its own ribbons leave.
_BEHIND = {"right": "e", "down": "s"}
_AHEAD = {"right": "w", "down": "n"}
_ASIDE = {"right": "s", "down": "e"}


def _draw(keys, metrics: _Metrics, placed: _Placed, faces, sizes: _Sizes,
          columns, direction: str, names: Sequence[_Name], color, tint: str,
          opacity: float, ease: float | None, name: str | None) -> Sankey:
    """Bars, ribbons and names, in that paint order, in one shared frame."""
    # Late, all of them, for the reason `inklet.graph` imports its theme late:
    # `inklet` imports `layout`, and `plot` imports `layout` too, so a top-level
    # import back into either would close a cycle at package import time.
    from .. import current_theme
    from ..diagnostics import abutting
    from ..draw.place import place
    from ..plot.ribbon import RIBBON_EASE, ribbon_between

    theme = current_theme()
    flow_axis = Vec2(1.0, 0.0) if direction == "right" else Vec2(0.0, 1.0)
    point = ((lambda a, b: Vec2(a, b)) if direction == "right"
             else (lambda a, b: Vec2(b, a)))
    slope = RIBBON_EASE if ease is None else float(ease)

    fills = [_pick(color, keys[i], i, theme.color) for i in range(metrics.count)]
    ribbons = [
        ribbon_between(
            point(placed.along[u], lo0), point(placed.along[u], hi0),
            point(placed.along[v], lo1), point(placed.along[v], hi1),
            along=flow_axis, ease=slope,
            fill=fills[u if tint == "source" else v], fill_opacity=opacity)
        for (u, v, _), (lo0, hi0, lo1, hi1) in zip(metrics.edges, faces)
    ]
    # `stroke="none"` rather than left alone: the page's own role puts the
    # theme's ink under everything that does not say otherwise, and an outlined
    # bar reads as a box with a border round it instead of as a quantity.
    bars = [
        Diagram(prim=RectPrim(*((sizes.node, placed.height[n]) if direction == "right"
                                else (placed.height[n], sizes.node))),
                kind=NODE_KIND).styled(fill=fills[n], stroke="none")
        for n in range(metrics.count)
    ]
    centres = [point(placed.along[n], placed.across[n] + placed.height[n] / 2.0)
               for n in range(metrics.count)]

    # One group, declared `abutting`, because every pair inside it touches on
    # purpose: a ribbon ends under the bar it feeds, and an interior name is
    # set over the ribbons its own bar sends out, on a halo, because in a
    # Sankey dense enough to be worth drawing there is nowhere else for it to
    # go. The claim is scoped to this subtree -- an annotation somebody adds
    # later is measured against the drawing exactly as before -- and `_sizes`
    # keeps the names clear of the bars and of each other by construction, so
    # what is being waived is only the one case the rule cannot judge.
    labels = _labels(metrics, placed, sizes, columns, direction, names, place)
    group = place([*ribbons, *zip(centres, bars), *labels],
                  kind=abutting(SANKEY_KIND))

    records = _records(keys, metrics, placed, sizes, columns, direction, bars,
                       names)
    return Sankey(
        diagram=group if name is None else group.named(name),
        nodes=records,
        flows=tuple(SankeyFlow(source=records[u], target=records[v],
                               value=value, diagram=ribbon)
                    for (u, v, value), ribbon in zip(metrics.edges, ribbons)),
        crossings=_crossings(_centre_lines(placed, metrics, faces)),
        unit=placed.unit,
        keys={key: index for index, key in enumerate(keys)},
    )


def _records(keys, metrics: _Metrics, placed: _Placed, sizes: _Sizes, columns,
             direction: str, bars: Sequence[Diagram],
             names: Sequence[_Name]) -> tuple[SankeyNode, ...]:
    slot = {node: index for column in columns for index, node in enumerate(column)}
    out = []
    for node in range(metrics.count):
        lo, hi = placed.across[node], placed.across[node] + placed.height[node]
        half = sizes.node / 2.0
        along = placed.along[node]
        box = (Rect(along - half, lo, along + half, hi) if direction == "right"
               else Rect(lo, along - half, hi, along + half))
        out.append(SankeyNode(
            key=keys[node], label=names[node].text, rank=metrics.ranks[node],
            order=slot[node], value=metrics.values[node], box=box,
            diagram=bars[node]))
    return tuple(out)


def _labels(metrics: _Metrics, placed: _Placed, sizes: _Sizes, columns,
            direction: str, names: Sequence[_Name], place) -> list[Diagram]:
    """The shaped names, put beside the bars they belong to.

    One `place` call per anchor, each in the same `origin=(0, 0)` frame as the
    bars, which is what keeps three groups of names in register with the
    drawing instead of each centring on its own box.
    """
    last = len(columns) - 1
    reach = sizes.node / 2.0 + sizes.label_gap
    groups: dict[str, list[tuple[Vec2, Diagram]]] = {}
    for node in range(metrics.count):
        block = names[node].block
        if block is None:
            continue
        rank = metrics.ranks[node]
        centre = placed.across[node] + placed.height[node] / 2.0
        if last > 0 and rank == 0:
            anchor = _BEHIND[direction]
            at = (placed.along[node] - reach, centre)
        elif last > 0 and rank == last:
            anchor = _AHEAD[direction]
            at = (placed.along[node] + reach, centre)
        else:
            anchor = _ASIDE[direction]
            at = (placed.along[node], placed.across[node] - sizes.label_gap)
        along, across = at
        put = (Vec2(along, across) if direction == "right"
               else Vec2(across, along))
        groups.setdefault(anchor, []).append((put, block))
    return [place(items, anchor=anchor, origin=(0.0, 0.0))
            for anchor, items in sorted(groups.items())]


def _pick(source, key, index: int, fallback) -> str:
    """A per-node value from a mapping, a function, or the theme."""
    if source is None:
        return fallback(index)
    if isinstance(source, Mapping):
        found = source.get(key)
        return fallback(index) if found is None else str(found)
    return str(source(key))
