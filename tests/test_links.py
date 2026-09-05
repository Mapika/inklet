"""Geometry tests for `inklet.links`, checked numerically.

Layouts are hand-placed with `core` alone -- no layout engine, no text, no
theme -- so every expected number below can be worked out on paper.
"""

from __future__ import annotations

import math

import pytest

from inklet.core import (
    Diagram, EllipsePrim, PathPrim, PhantomPrim, Placement, Rect, RectPrim,
    Style, Vec2, group, resolve,
)
from inklet.links import (
    CONNECTOR_KIND, DEFAULT_ARROW_SIZE, FLAG_COINCIDENT, FLAG_OVERLAP, FLAG_SHORT,
    FLAG_SOURCE_NO_TRACE, FLAG_ZERO_LENGTH, HEAD_KIND, LABEL_KIND, LINK_KIND,
    Link, LinkError, is_degenerate, link, link_ends, link_flags, route,
    route_all,
)

TOL = 1e-6


# -- fixtures and helpers -------------------------------------------------


def circle(r: float = 10.0) -> Diagram:
    return Diagram(prim=EllipsePrim(r, r))


def box(w: float = 20.0, h: float = 10.0, radius: float = 0.0) -> Diagram:
    return Diagram(prim=RectPrim(w, h, radius))


def figure(*nodes: Diagram) -> dict[str, Placement]:
    return resolve(group(nodes))


def nodes_of(routed: Diagram, kind: str) -> list[tuple[Diagram, Placement]]:
    places = resolve(routed)
    return [(n, places[n.id]) for n in routed.walk() if n.kind == kind]


def shaft(routed: Diagram) -> list[Vec2]:
    node, place = nodes_of(routed, CONNECTOR_KIND)[0]
    return [place.world.apply(p) for p in node.prim.subpaths[0].points]


def heads(routed: Diagram) -> list[list[Vec2]]:
    out = []
    for node, place in nodes_of(routed, HEAD_KIND):
        out.append([place.world.apply(p) for p in node.prim.subpaths[0].points])
    return out


def every_point(routed: Diagram) -> list[Vec2]:
    places = resolve(routed)
    pts: list[Vec2] = []
    for node in routed.walk():
        if isinstance(node.prim, PathPrim):
            world = places[node.id].world
            for sub in node.prim.subpaths:
                pts.extend(world.apply(p) for p in sub.points)
    return pts


def ends(routed: Diagram) -> tuple[Vec2, Vec2]:
    return routed.anchor_point("start"), routed.anchor_point("end")


def boundary_gap(p: Vec2, rect: Rect) -> float:
    """0 when p is on the rect's outline, negative inside, positive outside."""
    c = rect.center
    return max(abs(p.x - c.x) / (rect.width / 2), abs(p.y - c.y) / (rect.height / 2)) - 1.0


def close(a: Vec2, b: Vec2, tol: float = TOL) -> bool:
    return (a - b).length <= tol


# -- the test that proves arrows touch ------------------------------------


def test_circle_endpoints_sit_exactly_on_both_circles():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    start, end = ends(route(link(a, b), places))

    assert start.x == pytest.approx(10.0, abs=TOL)   # centre 0 + r
    assert start.y == pytest.approx(0.0, abs=TOL)
    assert end.x == pytest.approx(40.0, abs=TOL)     # centre 50 - r
    assert end.y == pytest.approx(0.0, abs=TOL)


def test_circle_endpoints_survive_a_reversed_link():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    start, end = ends(route(link(b, a), places))

    assert start.x == pytest.approx(40.0, abs=TOL)
    assert end.x == pytest.approx(10.0, abs=TOL)


# -- rectangles, rounded rectangles ---------------------------------------


def test_rect_endpoints_land_on_the_boundary_and_not_on_the_centres():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b.translated(40, 25))
    rect_a = Rect(-10, -5, 10, 5)
    rect_b = Rect(30, 20, 50, 30)

    start, end = ends(route(link(a, b), places))

    # The 40:25 diagonal leaves through the long edges, at y = +-5 from centre.
    assert close(start, Vec2(8.0, 5.0))
    assert close(end, Vec2(32.0, 20.0))
    assert boundary_gap(start, rect_a) == pytest.approx(0.0, abs=1e-9)
    assert boundary_gap(end, rect_b) == pytest.approx(0.0, abs=1e-9)
    assert not close(start, rect_a.center, tol=1.0)
    assert not close(end, rect_b.center, tol=1.0)


def test_rounded_rect_clips_on_the_round_not_the_sharp_corner():
    a = box(20, 10, radius=3.0)
    b = circle(2)
    places = figure(a, b.translated(40, 20))   # aimed straight at the corner

    start, _ = ends(route(link(a, b), places))

    sharp_corner = Vec2(10.0, 5.0)             # where an unrounded rect would clip
    assert not close(start, sharp_corner, tol=0.5)
    assert start.length < sharp_corner.length
    # On the fillet: the corner arc is centred at (7, 2) with radius 3, and the
    # trace polygon inscribes it (six steps, so never more than 0.3% inside).
    assert start.x > 7.0 and start.y > 2.0
    assert 3.0 * math.cos(math.radians(7.5)) <= (start - Vec2(7.0, 2.0)).length <= 3.0


def test_standoff_pulls_each_end_two_millimetres_off_the_shape():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    plain = ends(route(link(a, b), places))
    held = ends(route(link(a, b, standoff=2.0), places))

    assert held[0].x == pytest.approx(plain[0].x + 2.0, abs=TOL)
    assert held[1].x == pytest.approx(plain[1].x - 2.0, abs=TOL)
    assert held[0].y == pytest.approx(0.0, abs=TOL)
    assert held[1].y == pytest.approx(0.0, abs=TOL)


# -- arrow heads ----------------------------------------------------------


def test_head_tip_is_on_the_endpoint_and_the_shaft_stops_short():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    routed = route(link(a, b), places)
    _, end = ends(routed)
    (tip, *_), = heads(routed)
    line = shaft(routed)

    assert close(tip, end, tol=1e-9)
    assert line[-1].x < end.x
    assert (end - line[-1]).length == pytest.approx(DEFAULT_ARROW_SIZE, abs=TOL)
    assert line[0].x == pytest.approx(end.x - 30.0, abs=TOL)   # start end untouched


def test_double_gets_a_head_at_both_ends_pointing_outward():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    routed = route(link(a, b, kind="double"), places)
    start, end = ends(routed)
    tips = [h[0] for h in heads(routed)]
    line = shaft(routed)

    assert len(tips) == 2
    assert any(close(t, start, tol=1e-9) for t in tips)
    assert any(close(t, end, tol=1e-9) for t in tips)
    assert line[0].x == pytest.approx(start.x + DEFAULT_ARROW_SIZE, abs=TOL)
    assert line[-1].x == pytest.approx(end.x - DEFAULT_ARROW_SIZE, abs=TOL)


def test_line_kind_draws_no_head_and_no_inset():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    routed = route(link(a, b, kind="line"), places)
    start, end = ends(routed)

    assert heads(routed) == []
    assert close(shaft(routed)[0], start, tol=1e-9)
    assert close(shaft(routed)[-1], end, tol=1e-9)


def test_head_shapes_are_filled_paths_except_the_open_one():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    for name, filled in (("triangle", True), ("open", False), ("dot", True)):
        routed = route(link(a, b, head=name), places)
        node, _ = nodes_of(routed, HEAD_KIND)[0]
        assert node.prim.filled is filled, name

    dot = route(link(a, b, head="dot", arrow_size=4.0), places)
    node, _ = nodes_of(dot, HEAD_KIND)[0]
    sub = node.prim.subpaths[0]
    assert sub.closed and len(sub.curves) == 4          # real beziers for the SVG
    centre = ends(dot)[1]
    for first, _c1, _c2, _last in sub.curves:
        assert (first - centre).length == pytest.approx(1.2, abs=1e-12)
    for p in sub.points:
        # Flattened from the cubics, so on the circle to the kappa error (0.03%).
        assert (p - centre).length == pytest.approx(1.2, rel=1e-3)


def test_arrow_size_scales_the_head():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    routed = route(link(a, b, arrow_size=5.0), places)
    end = ends(routed)[1]

    assert (end - shaft(routed)[-1]).length == pytest.approx(5.0, abs=TOL)


# -- anchors --------------------------------------------------------------


def test_anchor_endpoints_are_used_verbatim():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    routed = route(link(a.at("e"), b.at("w"), standoff=3.0), places)
    start, end = ends(routed)

    assert close(start, Vec2(10.0, 0.0), tol=1e-12)   # exactly the anchor
    assert close(end, Vec2(40.0, 0.0), tol=1e-12)
    assert not is_degenerate(routed)


def test_an_anchored_source_still_clips_the_far_end():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    start, end = ends(route(link(a.at("n"), b), places))

    assert close(start, Vec2(0.0, -10.0), tol=1e-12)
    # Fired from b's centre back toward that anchor, so it lands on b's circle.
    assert (end - Vec2(50.0, 0.0)).length == pytest.approx(10.0, abs=TOL)


# -- orthogonal routing ---------------------------------------------------


def axis_aligned(points: list[Vec2]) -> bool:
    return all(abs(b.x - a.x) < 1e-9 or abs(b.y - a.y) < 1e-9
               for a, b in zip(points, points[1:]))


def test_orthogonal_z_elbow_is_axis_aligned_and_touches_both_shapes():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b.translated(60, 30))

    routed = route(link(a, b, route="orthogonal", kind="line"), places)
    points = shaft(routed)

    assert axis_aligned(points)
    assert len(points) == 4                       # a Z: out, across, in
    assert [(p.x, p.y) for p in points] == [(10, 0), (30, 0), (30, 30), (50, 30)]
    assert boundary_gap(points[0], Rect(-10, -5, 10, 5)) == pytest.approx(0, abs=1e-9)
    assert boundary_gap(points[-1], Rect(50, 25, 70, 35)) == pytest.approx(0, abs=1e-9)


def test_orthogonal_l_elbow_when_the_shapes_share_the_dominant_axis():
    a, b = box(30, 4), box(30, 4)
    places = figure(a, b.translated(20, 12))

    routed = route(link(a, b, route="orthogonal", kind="line"), places)
    points = shaft(routed)

    assert axis_aligned(points)
    assert len(points) == 3                       # an L: out east, turn, down
    assert [(p.x, p.y) for p in points] == [(15, 0), (20, 0), (20, 10)]
    assert boundary_gap(points[-1], Rect(5, 10, 35, 14)) == pytest.approx(0, abs=1e-9)


def test_orthogonal_clips_along_the_segment_not_the_centre_line():
    # A centre-to-centre clip would leave through the top-right of a; the first
    # segment runs due east, so the endpoint must be on the east edge instead.
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b.translated(60, 30))

    start = shaft(route(link(a, b, route="orthogonal", kind="line"), places))[0]

    assert start.y == pytest.approx(0.0, abs=1e-12)
    assert start.x == pytest.approx(10.0, abs=1e-12)


def test_orthogonal_head_follows_the_last_segment():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b.translated(0, 40))       # straight down

    routed = route(link(a, b, route="orthogonal"), places)
    points = shaft(routed)
    (tip, left, right), = heads(routed)

    assert axis_aligned(points)
    assert close(tip, ends(routed)[1], tol=1e-9)
    assert tip.y > left.y and tip.y > right.y     # pointing south, y grows down


def test_orthogonal_aligned_centres_stay_a_single_run():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b.translated(50, 0))

    points = shaft(route(link(a, b, route="orthogonal", kind="line"), places))

    assert len(points) == 2
    assert axis_aligned(points)


def test_orthogonal_corner_rounding_emits_real_curves():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b.translated(60, 30))

    routed = route(link(a, b, route="orthogonal", kind="line", corner=2.0), places)
    node, _ = nodes_of(routed, CONNECTOR_KIND)[0]
    sub = node.prim.subpaths[0]

    # The backend draws from `curves` alone when they exist, so the chain has to
    # run tip to tip without gaps: straight, fillet, straight, fillet, straight.
    assert len(sub.curves) == 5
    assert close(sub.curves[0][0], ends(routed)[0], tol=1e-9)
    assert close(sub.curves[-1][3], ends(routed)[1], tol=1e-9)
    for before, after in zip(sub.curves, sub.curves[1:]):
        assert close(before[3], after[0], tol=1e-12)
    assert close(sub.points[0], ends(routed)[0], tol=1e-9)
    assert close(sub.points[-1], ends(routed)[1], tol=1e-9)
    assert all(math.isfinite(p.x) and math.isfinite(p.y) for p in sub.points)
    # The fillets stay inside the elbow they replaced.
    assert all(9.9 <= p.x <= 50.1 for p in sub.points)


# -- leaders --------------------------------------------------------------


def test_leader_has_an_oblique_leg_a_horizontal_shoulder_and_a_dot():
    spot = Diagram(prim=RectPrim(30, 20)).anchor("tip", Vec2(-5, 5))
    label = box(12, 4)
    places = figure(spot, label.translated(40, -20))

    routed = route(link(spot.at("tip"), label, kind="leader"), places)
    points = shaft(routed)

    assert len(points) == 3
    assert close(points[0], Vec2(-5.0, 5.0), tol=1e-12)     # exactly the spot
    assert points[1].y == pytest.approx(points[2].y, abs=1e-12)   # flat shoulder
    assert points[2].x == pytest.approx(34.0, abs=TOL)      # the label's west edge
    node, _ = nodes_of(routed, HEAD_KIND)[0]
    dot = node.prim.subpaths[0]
    assert node.prim.filled and len(dot.curves) == 4     # a dot, not an arrow
    assert all((p - points[0]).length == pytest.approx(DEFAULT_ARROW_SIZE * 0.30,
                                                       rel=1e-3) for p in dot.points)


# -- labels ---------------------------------------------------------------


def test_label_sits_above_the_line_clear_of_it():
    a, b = circle(10), circle(10)
    text = box(8, 3)                              # stands in for shaped text
    places = figure(a, b.translated(50, 0))

    routed = route(link(a, b, label=text, label_offset=1.0), places)
    node, place = nodes_of(routed, LABEL_KIND)[0]
    bounds = place.bbox

    assert bounds.center.x == pytest.approx(25.0, abs=TOL)
    assert bounds.y1 == pytest.approx(-1.0, abs=TOL)        # 1mm clear, above
    assert bounds.width == pytest.approx(8.0, abs=TOL)


def test_label_side_start_and_end_stay_near_their_own_ends():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))

    at_start = nodes_of(route(link(a, b, label=box(8, 3), label_side="start"), places),
                        LABEL_KIND)[0][1].bbox
    at_end = nodes_of(route(link(a, b, label=box(8, 3), label_side="end"), places),
                      LABEL_KIND)[0][1].bbox

    assert at_start.center.x == pytest.approx(15.0, abs=TOL)   # 4 half + 1 offset
    assert at_end.center.x == pytest.approx(35.0, abs=TOL)
    assert at_start.y1 == pytest.approx(-1.0, abs=TOL)


def test_label_of_a_vertical_link_goes_east():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(0, 50))

    bounds = nodes_of(route(link(a, b, label=box(8, 3)), places), LABEL_KIND)[0][1].bbox

    assert bounds.x0 == pytest.approx(1.0, abs=TOL)
    assert bounds.center.y == pytest.approx(25.0, abs=TOL)


# -- degenerate cases -----------------------------------------------------


def test_empty_trace_falls_back_to_the_centre_and_says_so():
    ghost = Diagram(prim=PhantomPrim(Rect(-5, -5, 5, 5)))
    b = circle(10)
    places = figure(ghost, b.translated(40, 0))

    routed = route(link(ghost, b), places)
    start, end = ends(routed)

    assert close(start, Vec2(0.0, 0.0), tol=1e-12)      # the centre, unclipped
    assert end.x == pytest.approx(30.0, abs=TOL)        # the far end still clips
    assert FLAG_SOURCE_NO_TRACE in link_flags(routed)
    assert is_degenerate(routed)
    assert all(math.isfinite(p.x) and math.isfinite(p.y) for p in every_point(routed))


def test_coincident_centres_do_not_raise_or_produce_nan():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b)                              # both at the origin

    routed = route(link(a, b), places)
    flags = link_flags(routed)

    assert FLAG_COINCIDENT in flags
    assert FLAG_ZERO_LENGTH in flags
    assert heads(routed) == []
    for p in every_point(routed):
        assert math.isfinite(p.x) and math.isfinite(p.y)


def test_one_shape_containing_the_other_is_marked_not_reversed():
    outer, inner = box(60, 40), circle(3)
    places = figure(outer, inner.translated(10, 5))

    routed = route(link(outer, inner), places)
    start, end = ends(routed)

    assert FLAG_OVERLAP in link_flags(routed)
    assert close(start, end, tol=1e-12)                # collapsed, not backwards
    for p in every_point(routed):
        assert math.isfinite(p.x) and math.isfinite(p.y)


def test_coincident_centres_are_survivable_on_an_orthogonal_route():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b)

    routed = route(link(a, b, route="orthogonal"), places)

    assert FLAG_COINCIDENT in link_flags(routed)
    for p in every_point(routed):
        assert math.isfinite(p.x) and math.isfinite(p.y)


def test_a_link_shorter_than_its_head_keeps_a_visible_shaft():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(21, 0))            # 1mm of clear space

    routed = route(link(a, b, arrow_size=4.0), places)
    line = shaft(routed)

    assert (line[-1] - line[0]).length > 0.0
    assert FLAG_SHORT in link_flags(routed)


def test_linking_something_outside_the_figure_is_a_clear_error():
    a, b = circle(10), circle(10)
    places = figure(a)

    with pytest.raises(Exception) as caught:
        route(link(a, b), places)
    assert "not part of this figure" in str(caught.value)


def test_bad_spec_values_are_rejected_at_declaration_time():
    a, b = circle(10), circle(10)
    with pytest.raises(LinkError):
        link(a, b, kind="squiggle")
    with pytest.raises(LinkError):
        link(a, b, route="curvy")


# -- declared pass-throughs -----------------------------------------------


def test_a_pass_through_is_recorded_after_the_two_endpoints():
    """`attached_to` is a flat tuple of ids, so the order is the only thing
    telling an end of the arrow from a shape it runs over."""
    a, b = box(), box().translated(0.0, 60.0)
    over = box().translated(0.0, 30.0)
    routed = route(link(a, b, through=[over]), figure(a, b, over))

    assert routed.attached_to == (a.id, b.id, over.id)
    assert link_ends(routed.attached_to) == (a.id, b.id)


def test_a_pass_through_changes_no_geometry():
    """It is a declaration for the linter, not a routing instruction: the shaft
    was already going straight through, which is the whole point."""
    a, b = box(), box().translated(0.0, 60.0)
    over = box().translated(0.0, 30.0)
    places = figure(a, b, over)

    assert shaft(route(link(a, b, through=[over]), places)) == shaft(
        route(link(a, b), places))


def test_a_pass_through_may_be_given_as_an_anchor():
    a, b = box(), box().translated(0.0, 60.0)
    over = box().translated(0.0, 30.0)
    routed = route(link(a, b, through=[over.at("center")]), figure(a, b, over))

    assert routed.attached_to == (a.id, b.id, over.id)


# -- determinism and plumbing ---------------------------------------------


def test_routing_twice_gives_identical_coordinates():
    a, b, c = circle(10), box(20, 10), box(20, 10)
    root = group([a, b.translated(50, 0), c.translated(50, 40)])
    places = resolve(root)
    links = [
        link(a, b, label=box(8, 3)),
        link(b, c, route="orthogonal", kind="double", corner=1.5),
        link(a.at("s"), c, kind="leader"),
    ]

    first = [every_point(route(l, places)) for l in links]
    second = [every_point(route(l, places)) for l in links]

    assert [[(p.x, p.y) for p in run] for run in first] == \
           [[(p.x, p.y) for p in run] for run in second]


def test_route_all_keeps_the_given_order_and_matches_single_routes():
    a, b, c = circle(10), circle(10), circle(10)
    root = group([a, b.translated(50, 0), c.translated(0, 50)])
    places = resolve(root)
    links = [link(a, b), link(a, c)]

    overlay = route_all(links, places)
    solo = [route(l, places) for l in links]

    assert [child.kind for child in overlay.children] == [LINK_KIND, LINK_KIND]
    for routed, expected in zip(overlay.children, solo):
        assert [(p.x, p.y) for p in every_point(routed)] == \
               [(p.x, p.y) for p in every_point(expected)]


def test_style_passes_through_and_nothing_else_is_painted():
    a, b = circle(10), circle(10)
    places = figure(a, b.translated(50, 0))
    dashed = Style(stroke_dash=(1.0, 1.0))

    routed = route(link(a, b, style=dashed, name="a-to-b"), places)

    assert routed.style == dashed
    assert routed.name == "a-to-b"
    assert routed.kind == LINK_KIND
    for node in routed.walk():
        if node is routed:
            continue
        assert node.style.fill is None
        assert node.style.stroke is None
        assert node.style.stroke_width is None


def test_a_named_link_keeps_its_name_alongside_its_flags():
    a, b = box(20, 10), box(20, 10)
    places = figure(a, b)

    routed = route(link(a, b, name="broken"), places)

    assert routed.name.startswith("broken!")
    assert FLAG_COINCIDENT in link_flags(routed)


# -- loose style keywords -------------------------------------------------


def test_a_link_takes_loose_style_keywords():
    """`box`, `path` and `polyline` all take these; `link` used to TypeError.

    blind-02 found it by crashing, which is the wrong way to learn that one
    public constructor spells styling differently from its neighbours.
    """
    a, b = box(10, 6), box(10, 6)

    connector = link(a, b, stroke_dash=(1.1, 0.7), stroke="#c33")

    assert connector.style.stroke_dash == (1.1, 0.7)
    assert connector.style.stroke == "#c33"


def test_loose_keywords_reach_the_drawing():
    """The routed group carries the style, so the shaft and head inherit it."""
    a, b = box(10, 6), box(10, 6)
    root = group([a, b.translated(40, 0)])

    routed = route(link(a, b, stroke_dash=(1.1, 0.7)), resolve(root))

    assert routed.style.stroke_dash == (1.1, 0.7)


def test_an_explicit_style_wins_over_a_loose_keyword():
    a, b = box(10, 6), box(10, 6)

    connector = link(a, b, style=Style(stroke="#000"), stroke="#c33")

    assert connector.style.stroke == "#000"


def test_a_link_field_is_not_swallowed_as_style():
    """`corner` is a Link field, not a Style one -- the split must respect that."""
    a, b = box(10, 6), box(10, 6)

    connector = link(a, b, route="orthogonal", corner=1.5)

    assert connector.corner == 1.5
    assert connector.style == Link(source=a, target=b).style


def test_a_misspelled_keyword_is_refused_by_name():
    a, b = box(10, 6), box(10, 6)

    with pytest.raises(LinkError, match="strok"):
        link(a, b, strok="#c33")
