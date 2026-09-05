"""Graph layout: the four algorithms, and the invariants all of them owe.

The numbers a layout produces are not worth pinning -- tune a constant and
every one moves. What is worth pinning is the set of promises: the same input
gives the same millimetres, no two boxes overlap, a layered drawing runs
downhill, a tree is tidy, and the caller's handle on a node still resolves
after the graph has wrapped it.
"""

from __future__ import annotations

import re

import pytest

import inklet
from inklet.core import Diagram, RectPrim, resolve
from inklet.layout import Graph, GraphError, graph
from inklet.layout.graph_force import circular_positions, force_positions, remove_overlaps
from inklet.layout.graph_tree import tree_positions

# A DAG with a diamond, a long edge and two components' worth of fan-out.
EDGES = [
    ("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"), ("a", "e"),
    ("d", "f"), ("e", "f"), ("b", "g"), ("g", "h"), ("d", "h"),
]
KEYS = ["a", "b", "c", "d", "e", "f", "g", "h"]


def rect(w=20.0, h=10.0, name=None):
    node = Diagram(prim=RectPrim(w, h), kind="box")
    return node.named(name) if name else node


def nodes(sizes=None):
    """One box per key, with deliberately unequal sizes."""
    sizes = sizes or {}
    return {k: rect(*sizes.get(k, (14.0 + 3.0 * i, 8.0 + (i % 3) * 2.0)), name=k)
            for i, k in enumerate(KEYS)}


def boxes_of(g: Graph):
    """Every node's rectangle in the laid-out graph's own frame."""
    placements = resolve(g.diagram)
    return [placements[node.id].bbox for node in g.nodes]


def overlaps(a, b, slack=1e-9):
    return (a.x1 - b.x0 > slack and b.x1 - a.x0 > slack
            and a.y1 - b.y0 > slack and b.y1 - a.y0 > slack)


def assert_disjoint(g: Graph):
    rects = boxes_of(g)
    for i, first in enumerate(rects):
        for j in range(i + 1, len(rects)):
            assert not overlaps(first, rects[j]), (
                f"{g.layout}: nodes {i} and {j} overlap: {first} {rects[j]}")


# -- the invariants every layout owes -------------------------------------


@pytest.mark.parametrize("layout", ["layered", "tree", "force", "circular"])
def test_no_node_overlaps(layout):
    assert_disjoint(graph(nodes(), EDGES, layout=layout))


@pytest.mark.parametrize("layout", ["layered", "tree", "force", "circular"])
def test_deterministic_coordinates(layout):
    first = boxes_of(graph(nodes(), EDGES, layout=layout))
    second = boxes_of(graph(nodes(), EDGES, layout=layout))
    assert [(r.x0, r.y0, r.x1, r.y1) for r in first] == \
           [(r.x0, r.y0, r.x1, r.y1) for r in second]


@pytest.mark.parametrize("layout", ["layered", "tree", "force", "circular"])
def test_deterministic_svg(layout):
    def build():
        boxes = {k: inklet.box(k.upper()) for k in KEYS}
        g = graph(boxes, EDGES, layout=layout)
        fig = inklet.figure(width=120)
        g.add_to(fig)
        # Node ids carry a per-process counter, so two graphs built in one
        # session never share them. The geometry is what has to agree.
        return re.sub(r' id="[^"]*"', "", fig.to_svg())

    assert build() == build()


@pytest.mark.parametrize("layout", ["layered", "tree", "force", "circular"])
def test_handles_still_resolve(layout):
    items = nodes()
    g = graph(items, EDGES, layout=layout)
    placements = resolve(g.diagram)
    for key, node in items.items():
        assert g[key] is node                      # the very object, not a copy
        assert node.id in placements               # and it is on the page
    assert g.nodes == tuple(items.values())


@pytest.mark.parametrize("layout", ["layered", "tree", "force", "circular"])
def test_edges_route(layout):
    boxes = {k: inklet.box(k.upper()) for k in KEYS}
    g = graph(boxes, EDGES, layout=layout)
    fig = inklet.figure(width=140)
    links = g.add_to(fig)
    assert len(links) == len(EDGES)
    root, _ = fig.build()
    drawn = [n for n in _walk(root) if n.kind in ("connector", "link")]
    assert len(drawn) >= len(EDGES)


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


# -- layered ---------------------------------------------------------------


def test_layered_ranks_run_downhill():
    g = graph(nodes(), EDGES)
    rects = boxes_of(g)
    index = {k: i for i, k in enumerate(KEYS)}
    for source, target in EDGES:
        u, v = index[source], index[target]
        assert g.ranks[u] < g.ranks[v], f"{source} -> {target} does not descend"
        assert rects[u].y1 <= rects[v].y0 + 1e-9, f"{source} sits below {target}"


def test_layered_direction_transposes():
    # With square nodes the two drawings are each other transposed; with
    # oblong ones they are not, because the rank axis is spaced by whichever
    # dimension actually points along it.
    square = {k: rect(10.0, 10.0, name=k) for k in KEYS}
    down = graph(square, EDGES, direction="down")
    right = graph({k: rect(10.0, 10.0, name=k) for k in KEYS},
                  EDGES, direction="right")
    assert down.width == pytest.approx(right.height)
    assert down.height == pytest.approx(right.width)
    for a, b in zip(boxes_of(down), boxes_of(right)):
        assert a.center.x == pytest.approx(b.center.y)
        assert a.center.y == pytest.approx(b.center.x)


def test_layered_up_reverses_down():
    down = graph(nodes(), EDGES, direction="down")
    up = graph(nodes(), EDGES, direction="up")
    a, b = boxes_of(down), boxes_of(up)
    for first, second in zip(a, b):
        assert first.center.y == pytest.approx(-second.center.y)


def test_layered_long_edges_get_a_route_that_avoids():
    g = graph(nodes(), EDGES)
    spans = {(e.source.name, e.target.name): (e.span, e.route) for e in g.edges}
    assert any(span > 1 for span, _ in spans.values()), "no long edge to check"
    for (source, target), (span, route) in spans.items():
        want = "straight" if span == 1 else "avoid"
        assert route == want, f"{source} -> {target} spans {span}, routed {route}"


def test_layered_breaks_cycles_without_losing_edges():
    items = {k: rect(name=k) for k in "xyz"}
    g = graph(items, [("x", "y"), ("y", "z"), ("z", "x")])
    assert len(g.edges) == 3
    assert sorted(g.ranks) == [0, 1, 2]
    assert_disjoint(g)


def test_layered_respects_gaps():
    items = {k: rect(20.0, 10.0, name=k) for k in "abc"}
    g = graph(items, [("a", "b"), ("a", "c")], gap=12.0, rank_gap=17.0)
    rects = {k: r for k, r in zip("abc", boxes_of(g))}
    assert rects["b"].y0 - rects["a"].y1 == pytest.approx(17.0)
    assert abs(rects["c"].x0 - rects["b"].x1) == pytest.approx(12.0)


def test_layered_scales_to_a_deep_graph():
    items = {str(i): rect(12.0, 8.0, name=str(i)) for i in range(60)}
    edges = [(str(i), str(i + 1)) for i in range(59)]
    edges += [(str(i), str(i + 7)) for i in range(0, 50, 7)]
    g = graph(items, edges)
    assert_disjoint(g)
    assert max(g.ranks) >= 20


# -- tree ------------------------------------------------------------------


def test_tree_centres_a_parent_over_its_children():
    items = {k: rect(name=k) for k in "prst"}
    g = graph(items, [("p", "r"), ("p", "s"), ("p", "t")], layout="tree")
    rects = {k: r for k, r in zip("prst", boxes_of(g))}
    kids = [rects["r"], rects["s"], rects["t"]]
    middle = (min(r.x0 for r in kids) + max(r.x1 for r in kids)) / 2.0
    assert rects["p"].center.x == pytest.approx(middle)


def test_tree_subtrees_do_not_interleave():
    # Two bushy subtrees: every leaf of the left one must sit left of every
    # leaf of the right one, which is the whole point of a tidy tree.
    items = {k: rect(name=k) for k in ["root", "L", "R", "l1", "l2", "r1", "r2"]}
    g = graph(items, [("root", "L"), ("root", "R"), ("L", "l1"), ("L", "l2"),
                      ("R", "r1"), ("R", "r2")], layout="tree")
    rects = dict(zip(items, boxes_of(g)))
    assert max(rects["l1"].x1, rects["l2"].x1) <= min(rects["r1"].x0,
                                                      rects["r2"].x0) + 1e-9
    assert_disjoint(g)


def test_tree_is_compact_for_unequal_widths():
    items = {"p": rect(60.0, 10.0, name="p"), "a": rect(10.0, 10.0, name="a"),
             "b": rect(10.0, 10.0, name="b")}
    g = graph(items, [("p", "a"), ("p", "b")], layout="tree", gap=4.0)
    rects = dict(zip(items, boxes_of(g)))
    assert rects["b"].x0 - rects["a"].x1 == pytest.approx(4.0)


def test_tree_takes_an_explicit_root():
    items = {k: rect(name=k) for k in "abcd"}
    edges = [("a", "b"), ("b", "c"), ("c", "d")]
    high = graph(items, edges, layout="tree", roots=["d"])
    assert high.ranks[list(items).index("d")] == 0


def test_tree_covers_a_forest():
    items = {k: rect(name=k) for k in "abcd"}
    g = graph(items, [("a", "b"), ("c", "d")], layout="tree")
    assert_disjoint(g)
    assert set(g.ranks) == {0, 1}


# -- force and circular ----------------------------------------------------


def test_force_is_seed_free_and_repeatable():
    sizes = [(14.0, 9.0)] * 8
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (4, 5), (5, 6), (6, 7)]
    first = force_positions(sizes, edges, gap=5.0, iterations=120)
    second = force_positions(sizes, edges, gap=5.0, iterations=120)
    assert first == second


def test_force_puts_neighbours_nearer_than_strangers():
    items = {k: rect(12.0, 8.0, name=k) for k in "abcdef"}
    # Two triangles joined by nothing at all.
    g = graph(items, [("a", "b"), ("b", "c"), ("c", "a"),
                      ("d", "e"), ("e", "f"), ("f", "d")], layout="force")
    rects = dict(zip(items, boxes_of(g)))

    def far(p, q):
        first, second = rects[p].center, rects[q].center
        return ((first.x - second.x) ** 2 + (first.y - second.y) ** 2) ** 0.5

    assert far("a", "b") < far("a", "d") + far("a", "e") + far("a", "f")
    assert_disjoint(g)


def test_circular_puts_everything_on_one_ring():
    items = {k: rect(10.0, 10.0, name=k) for k in "abcdefgh"}
    g = graph(items, [], layout="circular")
    rects = boxes_of(g)
    centre_x = sum(r.center.x for r in rects) / len(rects)
    centre_y = sum(r.center.y for r in rects) / len(rects)
    radii = [((r.center.x - centre_x) ** 2 + (r.center.y - centre_y) ** 2) ** 0.5
             for r in rects]
    assert max(radii) - min(radii) < 1e-6
    assert_disjoint(g)


def test_overlap_removal_separates_a_pile():
    points = [(0.0, 0.0), (1.0, 0.5), (0.5, 1.0), (-0.5, 0.2)]
    sizes = [(20.0, 10.0)] * 4
    out = remove_overlaps(points, sizes, gap=2.0)
    for i in range(4):
        for j in range(i + 1, 4):
            assert (abs(out[i][0] - out[j][0]) >= 20.0 + 2.0 - 1e-6
                    or abs(out[i][1] - out[j][1]) >= 10.0 + 2.0 - 1e-6)


def test_circular_positions_are_ordered_by_input():
    ring = circular_positions([(10.0, 10.0)] * 4, gap=2.0)
    assert len(ring) == 4
    assert ring == circular_positions([(10.0, 10.0)] * 4, gap=2.0)


# -- the API surface -------------------------------------------------------


def test_nodes_may_be_a_plain_sequence_with_index_edges():
    items = [rect() for _ in range(4)]
    g = graph(items, [(0, 1), (1, 2), (2, 3)])
    assert g[0] is items[0]
    assert g.ranks == (0, 1, 2, 3)


def test_edges_may_carry_a_label_and_link_keywords():
    labelled = graph({k: inklet.box(k) for k in "ab"}, [("a", "b", "12 kHz")])
    assert labelled.edges[0].label is not None
    assert "label" in labelled.edges[0].link_kwargs()
    keyworded = graph({k: inklet.box(k) for k in "ab"}, [("a", "b", {"kind": "line"})])
    assert keyworded.edges[0].link_kwargs()["kind"] == "line"


def test_graph_diagram_composes_like_any_other():
    g = graph(nodes(), EDGES)
    stacked = inklet.vstack([inklet.title("a"), g.diagram], gap=3)
    assert any(node is g.diagram for node in _walk(stacked))
    assert stacked.height > g.height


def test_a_self_loop_is_drawn_as_a_loop_and_left_out_of_the_layout():
    items = {k: rect(name=k) for k in "ab"}
    plain = graph(items, [("a", "b")])
    looped = graph({k: rect(name=k) for k in "ab"}, [("a", "b"), ("a", "a")])

    assert looped.edges[1].link_kwargs()["loop"] == "auto"
    # The loop moved nothing: the two boxes sit exactly where they did.
    assert boxes_of(plain) == boxes_of(looped)


def test_opposing_edges_bow_to_opposite_sides():
    items = {k: rect(name=k) for k in "ab"}
    g = graph(items, [("a", "b"), ("b", "a")], lane=3)

    first = g.edges[0].link_kwargs()["offset"]
    second = g.edges[1].link_kwargs()["offset"]
    # Same sign, because each is measured from its own direction of travel --
    # which is what puts them either side of the line between the two boxes.
    assert first == second == pytest.approx(-1.5)


def test_repeated_edges_in_one_direction_are_spread_symmetrically():
    items = {k: rect(name=k) for k in "ab"}
    g = graph(items, [("a", "b"), ("a", "b"), ("a", "b")], lane=3)

    assert [e.link_kwargs()["offset"] for e in g.edges
            if "offset" in e.link_kwargs()] == [-3.0, 3.0]
    assert "offset" not in g.edges[1].link_kwargs()      # the middle one is straight


def test_the_same_diagram_twice_is_refused():
    shared = rect()
    with pytest.raises(GraphError, match="copy"):
        graph([shared, shared], [])


def test_unknown_layout_and_direction_say_what_is_allowed():
    items = {k: rect(name=k) for k in "ab"}
    with pytest.raises(GraphError, match="layered"):
        graph(items, [("a", "b")], layout="spiral")
    with pytest.raises(GraphError, match="down"):
        graph(items, [("a", "b")], direction="widdershins")


def test_unknown_endpoint_names_the_key():
    items = {k: rect(name=k) for k in "ab"}
    with pytest.raises(GraphError, match="zz"):
        graph(items, [("a", "zz")])


def test_empty_graph_is_an_empty_diagram():
    g = graph([], [])
    assert g.nodes == ()
    assert g.edges == ()


def test_a_single_node_needs_no_edges():
    only = rect(name="one")
    g = graph([only])
    assert g.width == pytest.approx(20.0)
    assert resolve(g.diagram)[only.id] is not None


def test_the_example_pipeline_lints_clean():
    # The shape of examples/graph.py, small enough to run in the suite.
    keys = ["src", "prep", "ref", "fit", "check", "plot", "out"]
    boxes = {k: inklet.box(k, width=15) for k in keys}
    edges = [("src", "prep"), ("ref", "prep"), ("prep", "fit"),
             ("fit", "check"), ("fit", "plot"), ("check", "out"),
             ("plot", "out"), ("prep", "out")]
    g = graph(boxes, edges, rank_gap=5, lane=4)
    fig = inklet.figure(width=inklet.COLUMN_SINGLE)
    g.add_to(fig)
    assert [d for d in fig.lint() if d.severity == "error"] == []


def test_links_property_matches_add_to():
    boxes = {k: inklet.box(k) for k in KEYS}
    g = graph(boxes, EDGES)
    specs = g.links
    assert len(specs) == len(EDGES)
    assert [s.route for s in specs] == [e.route for e in g.edges]


def test_tree_positions_is_usable_on_its_own():
    sizes = [(20.0, 10.0)] * 3
    points, levels = tree_positions(sizes, [(0, 1), (0, 2)], gap=4.0, rank_gap=6.0)
    assert levels == [0, 1, 1]
    assert points[0][0] == pytest.approx((points[1][0] + points[2][0]) / 2.0)


# -- settling, corridors and node-key waypoints ---------------------------


def test_settling_keeps_the_best_drawing_it_saw():
    """The sweeps are a search, not a fixed point.

    Weighted median plus isotonic repair is not a contraction: the repair can
    push a vertex past its own wish to make room for a rank-mate, the next
    rank reads the pushed position as its neighbour's wish, and the drawing
    walks sideways for as long as it is allowed to. The pass is therefore
    scored every sweep and the best drawing kept, which is what makes running
    it longer safe -- and what this test pins.
    """
    from inklet.layout import graph_layered as gl

    sizes = [(15.0, 8.0)] * 8
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (3, 4), (0, 5), (5, 6), (6, 4),
             (1, 7), (7, 4)]
    kw = dict(gap=4.0, rank_gap=5.0, lane=3.0)
    points, _, _ = gl.layered_positions(sizes, edges, **kw)
    width = max(x for x, _ in points) - min(x for x, _ in points)

    patched = gl._SETTLE_SWEEPS * 4
    old = gl._SETTLE_SWEEPS
    try:
        gl._SETTLE_SWEEPS = patched
        longer, _, _ = gl.layered_positions(sizes, edges, **kw)
    finally:
        gl._SETTLE_SWEEPS = old
    wider = max(x for x, _ in longer) - min(x for x, _ in longer)
    assert wider <= width + 1e-9


def test_a_corridor_sits_on_an_endpoint_when_there_is_room():
    """A long edge that runs straight down the page should bend once, not
    twice: parking the corridor halfway between its two endpoints buys a
    shorter arrow at the price of a jog at each end."""
    from inklet.layout import graph_layered as gl

    # `a` skips a rank to reach `d`; `b` and `c` fill the rank in between so
    # the corridor has somewhere to be, and nothing sits where `a` is.
    sizes = [(15.0, 8.0)] * 4
    edges = [(0, 1), (1, 2), (2, 3), (0, 3)]
    points, _, corridors = gl.layered_positions(sizes, edges, gap=4.0,
                                                rank_gap=5.0, lane=3.0)
    lane = [c for c in corridors if c]
    assert lane, "the skipping edge should have reserved a corridor"
    assert len({round(x, 6) for x, _ in lane[0]}) == 1   # slid as one piece
    assert points  # the rank neighbours here leave no room on either endpoint

    # The choice itself, where the room is not in question: an endpoint beats
    # the midpoint, the upper endpoint goes first, a blocked upper one hands
    # over to the lower, and two blocked ones hand back to the midpoint.
    assert gl._one_bend([0.0, 10.0], 5.0, -20.0, 20.0) == 0.0
    assert gl._one_bend([0.0, 10.0], 8.0, 7.0, 20.0) == 10.0
    assert gl._one_bend([0.0, 10.0], 5.0, 4.0, 6.0) == 5.0


def test_edge_waypoints_can_name_a_node():
    boxes = {k: inklet.box(k) for k in ("a", "b", "c")}
    edges = [("a", "b"), ("b", "c"),
             ("c", "a", {"waypoints": [("c", "e")]})]
    g = graph(boxes, edges, direction="down")
    spec = g.links[-1]
    assert len(spec.waypoints) == 1
    # It resolved to an anchor on the node, not to a bare pair of numbers.
    assert getattr(spec.waypoints[0], "name", None) == "e"


def test_a_named_waypoint_can_be_nudged():
    boxes = {k: inklet.box(k) for k in ("a", "b")}
    plain = graph(boxes, [("a", "b"), ("b", "a", {"waypoints": [("b", "e")]})],
                  direction="down")
    nudged = graph({k: inklet.box(k) for k in ("a", "b")},
                   [("a", "b"),
                    ("b", "a", {"waypoints": [(("b", "e"), 7.0, 0.0)]})],
                   direction="down")
    here = _waypoint_x(plain)
    there = _waypoint_x(nudged)
    assert there == pytest.approx(here + 7.0)


def _waypoint_x(g: Graph) -> float:
    from inklet.links.link import _via_point

    places = resolve(g.diagram)
    return _via_point(g.links[-1].waypoints[0], places).x


def test_an_unknown_waypoint_key_is_named_in_the_error():
    boxes = {k: inklet.box(k) for k in ("a", "b")}
    with pytest.raises(GraphError, match="nope"):
        graph(boxes, [("a", "b", {"waypoints": [("nope", "e")]})])
