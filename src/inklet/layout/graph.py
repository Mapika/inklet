"""`inklet.graph()` -- a diagram that arranges itself from its connectivity.

Every other combinator in this package is told the shape of the answer: a
`vstack` is a column because you asked for a column. A graph is not like that.
You know which box points at which, and the arrangement is a *consequence* of
that -- which is exactly the arithmetic this library exists to remove, and the
one place where removing it needs an algorithm rather than a rule.

The four layouts are not interchangeable, and picking between them is the only
real decision here:

* **layered** (the default) is Sugiyama: ranks along the flow direction, so
  every arrow points the same way and the reader can follow the process. It is
  the default because the graphs in papers are overwhelmingly *flows* --
  pipelines, protocols, causal diagrams -- and for a flow, "which way is
  forward" is the most important thing the picture says.
* **tree** is Reingold-Tilford, for a hierarchy that really is one: a taxonomy,
  a decision tree, a call graph from one entry point. It is tighter than
  layered on a true tree and says "this is a hierarchy" rather than "this is a
  process".
* **force** is Fruchterman-Reingold, for a graph with no direction to it --
  a correlation network, an interactome, an ontology neighbourhood. Use it when
  clusters are the message and the arrows are symmetric. Do not use it for a
  pipeline: it will happily draw step 5 above step 2.
* **circular** puts every node on one ring, which is the honest layout for a
  small dense graph where every layout is a hairball and at least this one is a
  legible hairball with the nodes in the order you wrote them.

The result **wraps, never rewrites**. The children of the returned diagram are
the very node objects handed in, so a handle taken before layout still resolves
afterwards and `fig.link(a, b)` finds `a`. What comes back is a `Graph`: the
diagram, the edges resolved to node pairs, and ready-made `Link` specs.

    g = inklet.graph(nodes, edges)
    g.add_to(fig)                       # content, then every edge routed

or, spelled out, if you want to do something else with the edges:

    fig.add(g.diagram)
    for e in g.edges:
        fig.link(e.source, e.target, label=e.label, route=e.route)

Nothing here draws an edge. Routing is `inklet.links`' job and stays its job: what
a layout owes the router is positions that leave room for an arrow, and for a
long edge in a layered drawing that means a reserved corridor, which is what
the dummy vertices are for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from ..core import Affine, Diagram, DiagramError, Rect, Vec2, mm
from ..links import Link, link as make_link
from .graph_force import circular_positions, force_positions
from .graph_layered import Point, layered_positions
from .graph_tree import spanning_tree_edges, tree_positions

__all__ = ["Graph", "GraphEdge", "GraphError", "graph", "LAYOUTS", "DIRECTIONS"]

Length = float | int | str

#: The layouts `graph()` knows, in the order they are worth reaching for.
LAYOUTS = ("layered", "tree", "force", "circular")

#: Which way a layered or tree drawing flows. Force and circular have no flow
#: direction, and say so rather than accepting the keyword and ignoring it.
DIRECTIONS = ("down", "up", "right", "left")

GRAPH_KIND = "graph"


class GraphError(DiagramError):
    """A graph that cannot be laid out as asked."""


@dataclass(frozen=True)
class GraphEdge:
    """One edge, resolved: the two node diagrams, and how to draw the arrow.

    `span` is how many ranks the edge crosses in a layered or tree drawing (1
    for a neighbour, more for a skip connection, 0 when the layout has no
    ranks). It is what decides `route`, and it is exposed because an author
    who wants to style the long ones differently should not have to work it
    out again.
    """

    source: Diagram
    target: Diagram
    label: Diagram | None = None
    route: str = "straight"
    span: int = 0
    options: Mapping[str, object] = field(default_factory=dict)

    def link_kwargs(self) -> dict[str, object]:
        """Everything but the endpoints, ready to splat into `fig.link`."""
        out: dict[str, object] = {"route": self.route}
        out.update(self.options)
        if self.label is not None:
            out["label"] = self.label
        return out


@dataclass(frozen=True)
class Graph:
    """What `inklet.graph()` returns: a laid-out diagram plus its edges.

    Two things, because a graph is two things. `diagram` goes on the page and
    is an ordinary `Diagram` in every respect -- stack it, pad it, frame it.
    `edges` is what has to be routed afterwards, and it cannot be part of the
    diagram for the reason the whole library is built around: an arrow's
    endpoints are a function of where things ended up.
    """

    diagram: Diagram
    nodes: tuple[Diagram, ...]
    edges: tuple[GraphEdge, ...]
    layout: str
    ranks: tuple[int, ...]
    keys: Mapping[str, int] = field(default_factory=dict)

    def add_to(self, figure, **overrides) -> list[Link]:
        """Put the graph on a figure and route every edge. The usual spelling.

        Routing goes through `figure.link`, so edge labels are shaped and
        plated by the figure's own theme -- which is why this is preferred to
        walking `links` by hand. Keywords here override the per-edge ones, so
        `g.add_to(fig, route="avoid")` sends the lot round the houses.
        """
        figure.add(self.diagram)
        out = []
        for edge in self.edges:
            kwargs = edge.link_kwargs()
            kwargs.update(overrides)
            out.append(figure.link(edge.source, edge.target, **kwargs))
        return out

    @property
    def links(self) -> tuple[Link, ...]:
        """The edges as `Link` specs, for `inklet.route_all` without a figure.

        Use this *or* `add_to`, not both: a label diagram placed twice is an
        error, and these specs share their labels with the ones `add_to` makes.
        """
        return tuple(make_link(edge.source, edge.target, **edge.link_kwargs())
                     for edge in self.edges)

    def __getitem__(self, key) -> Diagram:
        """A node by index, by name, or by itself -- whatever the edges used."""
        if isinstance(key, Diagram):
            return key
        if isinstance(key, int):
            return self.nodes[key]
        index = self.keys.get(key)
        if index is not None:
            return self.nodes[index]
        raise KeyError(key)

    @property
    def bbox(self) -> Rect:
        return self.diagram.bbox

    @property
    def width(self) -> float:
        return self.diagram.width

    @property
    def height(self) -> float:
        return self.diagram.height


def graph(nodes, edges: Iterable = (), *, layout: str = "layered",
          direction: str = "down", gap: Length | None = None,
          rank_gap: Length | None = None, lane: Length | None = None,
          roots: Sequence | None = None, iterations: int = 300,
          route: str = "auto", sweeps: int = 4, ports: bool = True,
          fit: Length | None = None, name: str | None = None) -> Graph:
    """Lay out a graph from its edges, and hand back the diagram and the arrows.

    `nodes` is a sequence of diagrams, or a mapping from key to diagram when
    you would rather write the edges as `("etl", "model")` than carry a list
    of handles. `edges` is a sequence of pairs -- each endpoint a node object,
    an index, a mapping key or a node's `name` -- optionally with a third item:
    a string or diagram is the edge's label, a mapping is extra keywords for
    `fig.link`.

    `layout` is `"layered"`, `"tree"`, `"force"` or `"circular"`; the module
    docstring says when each one is the right answer, and the short version is
    that a flow wants layered and a network wants force. `direction` turns a
    layered or tree drawing to run `"down"`, `"up"`, `"right"` or `"left"`.

    `gap` is the clear space between two neighbours in a rank and `rank_gap`
    the space between one rank and the next; both default to the theme's
    spacing scale, which is what keeps a graph looking like the stacks beside
    it. `lane` is how much room a long edge's corridor takes, and only a very
    dense drawing needs it changed.

    `route` decides how the arrows are drawn. The default `"auto"` sends an
    edge between neighbouring ranks straight, because there is nothing between
    them to avoid, and routes a longer one with `route="avoid"`, which is the
    only mode that will actually go round the boxes it passes. Force and
    circular drawings have no ranks, so their edges are straight; pass
    `route="avoid"` if you would rather they detoured.

    A self-loop is drawn as an arc off the least crowded side of its box, and
    repeated edges between one pair are bowed off the centre line by `lane`
    millimetres each way, so a state machine with a retry and a pair of
    opposing transitions draws as three visible arrows instead of raising.
    Neither takes part in the layout itself: a loop has no rank to cross and
    a second edge between the same two boxes pulls them no closer together.

    `fit` is the width the drawing has to come out in -- pass the column it
    is going into, `fit=inklet.COLUMN_SINGLE`, and the layered pass slides whole
    ranks sideways until the boxes are inside it. It does nothing at all to a
    drawing that already fits, and it is not a scale or a guarantee: a single
    rank too wide on its own stays too wide. Layered drawings only; a tree,
    force or circular layout has no ranks to slide.

    `ports` spreads the arrows leaving one box across its edge rather than
    starting them all at its centre, which is what keeps three outgoing
    branches from sharing a shaft. It applies to layered and tree drawings,
    where "which way is out" is a property of the layout; pass `ports=False`
    for the older look.
    """
    if layout not in LAYOUTS:
        raise GraphError(
            f"unknown graph layout {layout!r}; use one of {', '.join(LAYOUTS)}")
    if direction not in DIRECTIONS:
        raise GraphError(
            f"unknown graph direction {direction!r}; "
            f"use one of {', '.join(DIRECTIONS)}")

    items, keys = _node_list(nodes)
    pairs, extras = _edge_list(edges, items, keys)
    gap_mm, rank_gap_mm, lane_mm = _spacings(gap, rank_gap, lane)
    fit_mm = None if fit is None else mm(fit)
    if fit_mm is not None and fit_mm <= 0.0:
        raise GraphError(f"graph fit must be positive, got {fit_mm}")

    # The layout is solved on the simple graph underneath: a self-loop has no
    # rank to cross and a second edge between one pair says nothing new about
    # where the boxes go. Both are drawn from the positions it settles on.
    simple, slot = _simple_edges(pairs)
    boxes = [_box_of(node, index) for index, node in enumerate(items)]
    positions, ranks, corridors = _solve(
        layout, direction, boxes, simple, gap_mm, rank_gap_mm, lane_mm, roots,
        iterations, sweeps, items, keys, fit_mm)

    placed = _place(items, boxes, positions, name)
    lanes = _corridors(placed, corridors)
    offsets = _parallel_offsets(pairs, lane_mm)
    spread = (_port_spread(pairs, positions, boxes, ranks, direction)
              if ports and layout in ("layered", "tree") else {})
    # A tree layout arranges the spanning tree and nothing else, so its cross
    # links are the ones that have to go round something.
    branches = (spanning_tree_edges(len(items), simple,
                                    _root_indices(roots, items, keys))
                if layout == "tree" else frozenset())
    built = tuple(
        GraphEdge(
            source=items[u], target=items[v],
            label=_edge_label(extra.get("label")),
            route=_edge_route(route, layout, ranks, u, v, branches,
                              u == v or offsets[position] != 0.0),
            span=abs(ranks[v] - ranks[u]) if ranks else 0,
            options=_edge_options(extra, u, v, offsets[position],
                                  spread.get(position, (0.0, 0.0)),
                                  lanes[slot[position]] if slot[position] is not None
                                  else (), items, keys, position),
        )
        for position, ((u, v), extra) in enumerate(zip(pairs, extras))
    )
    return Graph(diagram=placed, nodes=tuple(items), edges=built,
                 layout=layout, ranks=tuple(ranks), keys=dict(keys))


# -- input ----------------------------------------------------------------


def _node_list(nodes) -> tuple[list[Diagram], dict[str, int]]:
    """The nodes as a list, plus whatever names the edges may use for them."""
    keys: dict[str, int] = {}
    if isinstance(nodes, Mapping):
        items = []
        for index, (key, node) in enumerate(nodes.items()):
            keys[str(key)] = index
            items.append(node)
    else:
        items = list(nodes)
    seen: dict[int, int] = {}
    for index, node in enumerate(items):
        if not isinstance(node, Diagram):
            raise TypeError(
                f"graph node {index} is a {type(node).__name__}, not a Diagram")
        if id(node) in seen:
            raise GraphError(
                f"graph was handed the same Diagram object as nodes "
                f"{seen[id(node)]} and {index}; use .copy() to place a shape twice")
        seen[id(node)] = index
        if node.name is not None:
            keys.setdefault(node.name, index)
    return items, keys


def _edge_list(edges: Iterable, items: Sequence[Diagram], keys: Mapping[str, int]
               ) -> tuple[list[tuple[int, int]], list[dict]]:
    by_object = {id(node): index for index, node in enumerate(items)}
    pairs: list[tuple[int, int]] = []
    extras: list[dict] = []
    for position, spec in enumerate(edges):
        source, target, extra = _unpack(spec, position)
        u = _resolve(source, by_object, keys, items, position, "source")
        v = _resolve(target, by_object, keys, items, position, "target")
        pairs.append((u, v))
        extras.append(extra)
    return pairs, extras


def _simple_edges(pairs: Sequence[tuple[int, int]]
                  ) -> tuple[list[tuple[int, int]], list[int | None]]:
    """The graph a layout can solve, and where each edge went in it.

    A self-loop and a repeated edge are drawings, not structure: neither says
    anything about which box belongs above which. They are dropped here and
    put back by `route`, and the slot list is what lets an edge find the
    corridor its representative was given.
    """
    seen: dict[tuple[int, int], int] = {}
    simple: list[tuple[int, int]] = []
    slot: list[int | None] = []
    for u, v in pairs:
        if u == v:
            slot.append(None)
            continue
        where = seen.get((u, v))
        if where is None:
            where = seen[(u, v)] = len(simple)
            simple.append((u, v))
        slot.append(where)
    return simple, slot


def _edge_options(extra: Mapping[str, object], u: int, v: int, offset: float,
                  ports: tuple[float, float], lane: Sequence,
                  nodes: Sequence[Diagram] = (),
                  keys: Mapping[str, int] = {},
                  position: int = 0) -> dict[str, object]:
    """The keywords this edge needs beyond its endpoints, author first.

    Anything the author wrote on the edge wins: a `{'loop': 'e'}` in the edge
    list is a decision, and the automatic side is only a default.
    """
    out: dict[str, object] = {}
    if u == v:
        out["loop"] = "auto"
    if offset:
        out["offset"] = offset
    if ports[0]:
        out["port"] = ports[0]
    if ports[1]:
        out["target_port"] = ports[1]
    if lane:
        out["waypoints"] = lane
    out.update({k: value for k, value in extra.items() if k != "label"})
    if "waypoints" in extra:
        out["waypoints"] = _edge_waypoints(extra["waypoints"], nodes, keys,
                                           position)
    return out


def _edge_waypoints(spec, nodes: Sequence[Diagram],
                    keys: Mapping[str, int], position: int) -> tuple:
    """An edge's via-points, with node references spelled against the graph.

    Three spellings, and the reason for the last two is that a route written in
    raw millimetres is a route that stops being right the moment a box changes
    size. A bare `(x, y)` is millimetres in the frame the router sees, which is
    the laid-out content's own -- for a figure that is nothing but the graph,
    the graph's centre is the origin, and that is worth knowing before writing
    one. `("failed", "e")` is the east side of the node keyed `failed`,
    wherever the layout put it, and `(("failed", "e"), 8, 0)` is 8mm clear of
    it, which is what a margin actually is.
    """
    out = []
    for item in spec:
        if _is_node_ref(item):
            out.append(_node_anchor(item, nodes, keys, position))
        elif (isinstance(item, (tuple, list)) and len(item) == 3
              and _is_node_ref(item[0])):
            out.append((_node_anchor(item[0], nodes, keys, position),
                        float(item[1]), float(item[2])))
        else:
            out.append(item)
    return tuple(out)


def _is_node_ref(item) -> bool:
    """Is this `(node, anchor)` rather than a coordinate pair?

    Told apart by the anchor name: `(26, 0)` is two numbers and `("failed",
    "e")` names a compass point, so no pair is ever both.
    """
    return (isinstance(item, (tuple, list)) and len(item) == 2
            and isinstance(item[1], str))


def _node_anchor(item, nodes: Sequence[Diagram], keys: Mapping[str, int],
                 position: int):
    ref, name = item
    by_object = {id(node): index for index, node in enumerate(nodes)}
    index = _resolve(ref, by_object, keys, nodes, position, "waypoint of")
    return nodes[index].at(name)


def _parallel_offsets(pairs: Sequence[tuple[int, int]],
                      lane: float) -> list[float]:
    """How far each of several edges between one pair bows off the line.

    Symmetric about the centre line, and signed in the *pair's* order rather
    than the edge's, so an edge and its opposite come out on opposite sides of
    the line instead of both bowing to the reader's left.
    """
    groups: dict[tuple[int, int], list[int]] = {}
    for position, (u, v) in enumerate(pairs):
        if u != v:
            groups.setdefault((min(u, v), max(u, v)), []).append(position)
    out = [0.0] * len(pairs)
    for members in groups.values():
        if len(members) < 2:
            continue
        middle = (len(members) - 1) / 2.0
        for slot, position in enumerate(members):
            u, v = pairs[position]
            out[position] = (1.0 if u < v else -1.0) * (slot - middle) * lane
    return out


#: How much of a box's edge the ports leaving it may use. Three fifths keeps
#: the outermost shaft a comfortable distance inside the corner, where an
#: arrowhead and a rounded corner would otherwise argue.
_PORT_SPAN = 0.6


def _port_spread(pairs: Sequence[tuple[int, int]],
                 positions: Sequence[tuple[float, float]],
                 boxes: Sequence[Rect], ranks: Sequence[int],
                 direction: str) -> dict[int, tuple[float, float]]:
    """Where along its box's edge each edge starts and ends, for the boxes
    with several.

    Only edges leaving one box *the same way* are spread: an arrow going back
    up the page leaves through a different side and has the whole of it to
    itself. Within a group they are ordered by where they are going, so the
    ports come out in the same order as the targets and no two shafts cross
    before they have left the box. Arrivals are the same rule read backwards,
    and they matter more: four arrows converging on one box all clip its top
    edge at the same millimetre, which is a smudge rather than four arrows.
    """
    if not ranks:
        return {}
    vertical = direction in ("down", "up")
    leaving: dict[tuple[int, int], list[int]] = {}
    landing: dict[tuple[int, int], list[int]] = {}
    for position, (u, v) in enumerate(pairs):
        if u == v:
            continue
        way = 0 if ranks[v] == ranks[u] else (1 if ranks[v] > ranks[u] else -1)
        leaving.setdefault((u, way), []).append(position)
        landing.setdefault((v, way), []).append(position)

    def across(index: int) -> float:
        return positions[index][0] if vertical else positions[index][1]

    out: dict[int, list[float]] = {}
    for side, groups in enumerate((leaving, landing)):
        for (node, _), members in groups.items():
            if len(members) < 2:
                continue
            box = boxes[node]
            span = (box.width if vertical else box.height) * _PORT_SPAN
            members.sort(key=lambda position: (across(pairs[position][1 - side]),
                                               position))
            for slot, position in enumerate(members):
                slid = span * (slot / (len(members) - 1) - 0.5)
                out.setdefault(position, [0.0, 0.0])[side] = slid
    return {position: (values[0], values[1]) for position, values in out.items()}


def _corridors(placed: Diagram,
               corridors: Sequence[Sequence[tuple[float, float]]]) -> list[tuple]:
    """The layout's reserved lanes as anchors on the graph, so a link can be
    routed through them wherever the graph itself ends up on the page.

    Anchors rather than raw points, because the graph is a diagram like any
    other: it gets stacked, padded and centred after this, and a waypoint in
    the layout's own millimetres would be a waypoint somewhere else by the
    time the link is routed.
    """
    out: list[tuple] = []
    for index, points in enumerate(corridors):
        refs = []
        for step, (x, y) in enumerate(points):
            name = f"lane{index}-{step}"
            placed.anchor(name, Vec2(x, y))
            refs.append(placed.at(name))
        out.append(tuple(refs))
    return out


def _unpack(spec, position: int):
    if isinstance(spec, Mapping):
        extra = {k: v for k, v in spec.items() if k not in ("source", "target")}
        try:
            return spec["source"], spec["target"], extra
        except KeyError as exc:
            raise GraphError(
                f"edge {position} is a mapping without a {exc.args[0]!r} key"
            ) from None
    try:
        parts = tuple(spec)
    except TypeError:
        raise GraphError(
            f"edge {position} is a {type(spec).__name__}, not a pair of nodes"
        ) from None
    if len(parts) == 2:
        return parts[0], parts[1], {}
    if len(parts) == 3:
        third = parts[2]
        extra = dict(third) if isinstance(third, Mapping) else {"label": third}
        return parts[0], parts[1], extra
    raise GraphError(
        f"edge {position} has {len(parts)} items; an edge is "
        "(source, target) with an optional label or keyword mapping")


def _resolve(ref, by_object: Mapping[int, int], keys: Mapping[str, int],
             items: Sequence[Diagram], position: int, side: str) -> int:
    where = (f"root {position}" if side == "root"
             else f"the {side} of edge {position}")
    if isinstance(ref, Diagram):
        index = by_object.get(id(ref))
        if index is None:
            raise GraphError(
                f"{where} is not one of the nodes handed to graph()")
        return index
    if isinstance(ref, int) and not isinstance(ref, bool):
        if -len(items) <= ref < len(items):
            return ref % len(items)
        raise GraphError(
            f"{where} is index {ref}, outside the {len(items)} nodes given")
    if isinstance(ref, str):
        if ref in keys:
            return keys[ref]
        raise GraphError(
            f"{where} names {ref!r}, which is neither a key of the node "
            "mapping nor the name of any node given")
    raise TypeError(
        f"{where} is a {type(ref).__name__}; "
        "use the node itself, its index, or its name")


def _describe(node: Diagram, index: int) -> str:
    return f"{node.name!r}" if node.name else f"node {index}"


def _spacings(gap, rank_gap, lane) -> tuple[float, float, float]:
    """Theme spacing unless told otherwise. Geometry is decided while shapes
    are made, so this is the moment the tokens apply."""
    from .. import current_theme          # late: inklet imports layout, not back

    theme = current_theme()
    gap_mm = theme.gap("l") if gap is None else mm(gap)
    rank_mm = theme.gap("xl") if rank_gap is None else mm(rank_gap)
    lane_mm = max(2.0, gap_mm / 2.0) if lane is None else mm(lane)
    for label, value in (("gap", gap_mm), ("rank_gap", rank_mm), ("lane", lane_mm)):
        if value < 0.0:
            raise GraphError(f"{label} cannot be negative, got {value}")
    return gap_mm, rank_mm, lane_mm


def _box_of(node: Diagram, index: int) -> Rect:
    box = node.envelope.bbox()
    if box is None:
        raise GraphError(
            f"graph node {index} is empty, so it has no size to lay out; "
            "use inklet.spacer() for a node that is deliberately blank")
    return box


def _edge_label(value):
    """A string label is shaped now, with the theme in force, exactly as
    `inklet.box` shapes the text inside a box. Anything else is passed along."""
    if value is None or isinstance(value, Diagram):
        return value
    from .. import label as make_label     # late, for the same reason

    return make_label(str(value))


def _edge_route(route: str, layout: str, ranks: Sequence[int],
                u: int, v: int, branches: frozenset[tuple[int, int]],
                curved: bool = False) -> str:
    """Straight where nothing is in the way, `avoid` where something is.

    A layered drawing puts a corridor between neighbouring ranks and nothing
    else in it, so a one-rank edge is a clean straight line. An edge that skips
    ranks passes the boxes in between, and only `route="avoid"` will actually
    go round them -- an elbow would turn once and drive straight through. A
    tree draws its branches and detours everything else, which is the same
    rule read off the spanning tree instead of off the ranks.
    """
    if route != "auto":
        return route
    if curved:
        # A loop and a bowed parallel edge are curves; there is no polyline
        # for a mode to choose the shape of.
        return "straight"
    if layout in ("force", "circular") or not ranks:
        return "straight"
    if layout == "tree":
        return "straight" if (u, v) in branches else "avoid"
    return "straight" if abs(ranks[v] - ranks[u]) <= 1 else "avoid"


# -- solving --------------------------------------------------------------


def _solve(layout: str, direction: str, boxes: Sequence[Rect],
           pairs: Sequence[tuple[int, int]], gap: float, rank_gap: float,
           lane: float, roots, iterations: int, sweeps: int,
           items: Sequence[Diagram], keys: Mapping[str, int],
           fit: float | None = None
           ) -> tuple[list[Point], list[int], list[list[Point]]]:
    """Positions in figure coordinates, a rank per node (empty if none), and
    the corridor each edge was given (empty unless the layout reserves them)."""
    if not boxes:
        return [], [], []

    if layout in ("force", "circular"):
        sizes = [(box.width, box.height) for box in boxes]
        if layout == "circular":
            points = circular_positions(sizes, gap=gap)
        else:
            points = force_positions(sizes, pairs, gap=gap,
                                     iterations=max(0, iterations))
        return list(points), [], [[] for _ in pairs]

    # Layered and tree solve in (across, along): across the ranks and along the
    # flow. One transform at the end is the whole of what `direction` means,
    # and it is why neither algorithm has a compass direction in it.
    vertical = direction in ("down", "up")
    sizes = [(box.width, box.height) if vertical else (box.height, box.width)
             for box in boxes]
    if layout == "layered":
        points, ranks, lanes = layered_positions(sizes, pairs, gap=gap,
                                                 rank_gap=rank_gap, lane=lane,
                                                 sweeps=sweeps, fit=fit)
    else:
        points, ranks = tree_positions(sizes, pairs, gap=gap, rank_gap=rank_gap,
                                       roots=_root_indices(roots, items, keys))
        lanes = [[] for _ in pairs]
    return ([_orient(direction, u, v) for u, v in points], list(ranks),
            [[_orient(direction, u, v) for u, v in lane] for lane in lanes])


def _root_indices(roots, items: Sequence[Diagram],
                  keys: Mapping[str, int]) -> list[int] | None:
    """Which nodes a tree hangs from. None means "whatever has no parent"."""
    if roots is None:
        return None
    by_object = {id(node): index for index, node in enumerate(items)}
    return [_resolve(ref, by_object, keys, items, position, "root")
            for position, ref in enumerate(roots)]


def _orient(direction: str, across: float, along: float) -> tuple[float, float]:
    if direction == "down":
        return across, along
    if direction == "up":
        return across, -along
    if direction == "right":
        return along, across
    return -along, across


# -- placing --------------------------------------------------------------


def _place(items: Sequence[Diagram], boxes: Sequence[Rect],
           positions: Sequence[tuple[float, float]], name: str | None) -> Diagram:
    """Wrap each node in a parent that puts its box centre on its position.

    `placed` rather than a rewrite, so the caller's handle on a node is the
    same object that ends up in the tree -- the promise every combinator here
    makes, and the one that lets `fig.link(a, b)` work after layout.
    """
    children = []
    span: Rect | None = None
    for node, box, (x, y) in zip(items, boxes, positions):
        centre = box.center
        child = node.placed(Affine.translation(x - centre.x, y - centre.y))
        children.append(child)
        here = child.envelope.bbox()
        if here is not None:
            span = here if span is None else span.union(here)
    # Centred on its own origin, like every other laid-out diagram here, so it
    # drops into the next stack without an anchor correction.
    offset = (Affine.translation(-span.center.x, -span.center.y)
              if span is not None else Affine.translation(0.0, 0.0))
    out = Diagram(children=tuple(children), kind=GRAPH_KIND, transform=offset)
    return out if name is None else out.named(name)
