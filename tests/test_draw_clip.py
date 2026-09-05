"""Geometric clipping.

The interesting cases are the ones where clipping is not simply "draw less":
a chain that leaves the region and comes back must come back as a *second*
piece, a node that was untouched must come back as the same object so the
caller's handle still works, and a region that is not convex must be refused
rather than quietly clipped to its own hull.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import IDENTITY, Diagram, PathPrim, Rect, RectPrim, Subpath, Vec2, resolve
from inklet.draw.clip import (clip_polygon, clip_polyline, clip_rings,
                           polygon_area, _region, _signed_area)

BOX = Rect(0.0, 0.0, 10.0, 10.0)


def edges_of(region):
    return _region(region)[0]


def world_points(node: Diagram) -> list[list[tuple[float, float]]]:
    """Every clipped subpath, in the frame the clip was expressed in."""
    placed = resolve(node)
    out = []
    for child in node.walk():
        if isinstance(child.prim, PathPrim):
            world = placed[child.id].world
            for sub in child.prim.subpaths:
                out.append([(round(world.apply(p).x, 6), round(world.apply(p).y, 6))
                            for p in sub.points])
    return out


def raw(points, *, closed=False, filled=False) -> Diagram:
    """A path whose coordinates are its own, with no centring applied."""
    return Diagram(prim=PathPrim((Subpath(tuple(Vec2(*p) for p in points), closed),),
                                 filled=filled))


# -- the algorithms on their own ------------------------------------------

def test_a_polygon_is_cut_to_the_corner_it_shares():
    square = [Vec2(5, 5), Vec2(15, 5), Vec2(15, 15), Vec2(5, 15)]

    ring = clip_polygon(square, edges_of(BOX))

    assert sorted((p.x, p.y) for p in ring) == [
        (5.0, 5.0), (5.0, 10.0), (10.0, 5.0), (10.0, 10.0)]


def test_a_chain_that_leaves_and_returns_comes_back_in_two_pieces():
    chain = [Vec2(1, 5), Vec2(-5, 5), Vec2(-5, 8), Vec2(1, 8)]

    pieces = clip_polyline(chain, edges_of(BOX))

    assert len(pieces) == 2
    assert [(p.x, p.y) for p in pieces[0]] == [(1.0, 5.0), (0.0, 5.0)]
    assert [(p.x, p.y) for p in pieces[1]] == [(0.0, 8.0), (1.0, 8.0)]


def test_a_chain_wholly_inside_is_one_piece_and_keeps_its_points():
    chain = [Vec2(1, 1), Vec2(5, 5), Vec2(9, 1)]

    pieces = clip_polyline(chain, edges_of(BOX))

    assert len(pieces) == 1
    assert [(p.x, p.y) for p in pieces[0]] == [(1, 1), (5, 5), (9, 1)]


def test_a_segment_running_along_the_boundary_survives():
    pieces = clip_polyline([Vec2(0, 0), Vec2(10, 0)], edges_of(BOX))

    assert len(pieces) == 1
    assert [(p.x, p.y) for p in pieces[0]] == [(0.0, 0.0), (10.0, 0.0)]


def test_a_triangle_region_cuts_on_its_diagonal():
    triangle = [(0, 0), (10, 0), (0, 10)]
    ring = clip_polygon([Vec2(0, 0), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)],
                        edges_of(triangle))

    assert sorted((round(p.x, 6), round(p.y, 6)) for p in ring) == [
        (0.0, 0.0), (0.0, 10.0), (10.0, 0.0)]


# -- the region -----------------------------------------------------------

def test_a_concave_region_is_refused():
    arrow = [(0, 0), (10, 0), (10, 10), (5, 4), (0, 10)]

    with pytest.raises(ValueError, match="convex"):
        inklet.clip(inklet.polyline([(0, 0), (1, 1)]), arrow)


def test_a_region_needs_three_corners():
    with pytest.raises(ValueError, match="three"):
        inklet.clip(inklet.polyline([(0, 0), (1, 1)]), [(0, 0), (1, 1)])


def test_winding_does_not_matter():
    forward = clip_polygon([Vec2(5, 5), Vec2(15, 5), Vec2(15, 15)],
                           edges_of([(0, 0), (10, 0), (10, 10), (0, 10)]))
    backward = clip_polygon([Vec2(5, 5), Vec2(15, 5), Vec2(15, 15)],
                            edges_of([(0, 10), (10, 10), (10, 0), (0, 0)]))

    assert sorted((p.x, p.y) for p in forward) == sorted((p.x, p.y) for p in backward)


# -- the tree walk --------------------------------------------------------

def test_something_wholly_inside_is_the_very_same_object():
    """The handle a caller is holding has to keep working, so a node that was
    not actually cut must not be rebuilt."""
    inside = raw([(2, 2), (8, 8)])

    cut = inklet.clip(inside, BOX)

    assert cut.children == (inside,)
    assert cut.children[0] is inside


def test_something_wholly_outside_is_dropped():
    cut = inklet.clip(raw([(20, 20), (30, 30)]), BOX)

    assert cut.children == ()
    assert cut.is_empty


def test_a_node_keeps_its_transform_when_its_geometry_is_cut():
    line = raw([(-5, 0), (15, 0)]).translated(0.0, 3.0)

    cut = inklet.clip(line, BOX)

    assert world_points(cut) == [[(0.0, 3.0), (10.0, 3.0)]]


def test_clipping_survives_a_rotation():
    line = raw([(-20, 0), (20, 0)]).rotated(90.0).translated(5.0, 5.0)

    cut = inklet.clip(line, BOX)

    (piece,) = world_points(cut)
    assert sorted(piece) == [(5.0, 0.0), (5.0, 10.0)]


def test_a_rectangle_cut_by_the_region_becomes_a_path():
    node = Diagram(prim=RectPrim(20.0, 4.0), transform=IDENTITY).translated(5.0, 5.0)

    cut = inklet.clip(node, BOX)

    (ring,) = world_points(cut)
    assert sorted(ring) == [(0.0, 3.0), (0.0, 7.0), (10.0, 3.0), (10.0, 7.0)]


def test_a_marker_on_the_boundary_is_kept_whole_by_default():
    """An ellipse cannot be cut into an ellipse. A scatter point half over the
    axis stays a round dot, which is what a journal prints."""
    point = inklet.marker("circle", 2.0).translated(10.0, 5.0)

    kept = inklet.clip(point, BOX)
    dropped = inklet.clip(point, BOX, strict=True)

    assert kept.bbox.x1 == pytest.approx(11.0)
    assert dropped.is_empty


def test_text_straddling_the_edge_is_kept_whole_but_can_be_dropped():
    label = inklet.label("spilling over").translated(10.0, 5.0)

    assert not inklet.clip(label, BOX).is_empty
    assert inklet.clip(label, BOX, strict=True).is_empty


def test_children_are_clipped_independently():
    group = Diagram(children=(
        raw([(2, 2), (4, 4)]),          # inside
        raw([(20, 2), (24, 4)]),        # outside
        raw([(8, 5), (14, 5)]),         # cut
    ))

    cut = inklet.clip(group, BOX)

    assert world_points(cut) == [[(2.0, 2.0), (4.0, 4.0)], [(8.0, 5.0), (10.0, 5.0)]]


def test_a_clipped_curve_reports_the_clipped_extent():
    """The envelope has to shrink, or `hstack` would pack against ink that is
    no longer there -- the whole reason for cutting points instead of emitting
    an SVG clipPath."""
    wide = raw([(-40, 5), (40, 5)])

    assert inklet.clip(wide, BOX).bbox.width == pytest.approx(10.0)


def test_clipping_is_deterministic():
    def build():
        star = inklet.curve([(1, 1), (14, 3), (5, 12), (-4, 6)], closed=True, fill="#ccc")
        return inklet.clip(star, BOX)

    assert world_points(build()) == world_points(build())


# -- a filled shape the region cuts in two ---------------------------------

U = [(0, 0), (10, 0), (10, 10), (8, 10), (8, 2), (2, 2), (2, 10), (0, 10)]
ACROSS_THE_ARMS = Rect(-1.0, 4.0, 11.0, 11.0)


def filled(points, closed=True) -> Diagram:
    return Diagram(prim=PathPrim(
        (Subpath(tuple(Vec2(*p) for p in points), closed),), filled=True))


def test_a_u_cut_across_both_arms_comes_back_as_two_rings():
    """The bug. Sutherland-Hodgman answers with one ring joined by a zero-width
    bridge along y = 4: right as a nonzero fill, wrong as a stroke, wrong under
    even-odd, and not the geometry anyone downstream measures."""
    rings = clip_rings([[Vec2(*p) for p in U]], edges_of(ACROSS_THE_ARMS))

    assert len(rings) == 2
    assert sorted(sorted((p.x, p.y) for p in ring) for ring in rings) == [
        [(0.0, 4.0), (0.0, 10.0), (2.0, 4.0), (2.0, 10.0)],
        [(8.0, 4.0), (8.0, 10.0), (10.0, 4.0), (10.0, 10.0)],
    ]


def test_the_bridge_is_gone_from_the_path_that_gets_drawn():
    cut = inklet.clip(filled(U), ACROSS_THE_ARMS)

    assert world_points(cut) == [
        [(10.0, 4.0), (10.0, 10.0), (8.0, 10.0), (8.0, 4.0)],
        [(2.0, 4.0), (2.0, 10.0), (0.0, 10.0), (0.0, 4.0)],
    ]


def test_sutherland_hodgman_still_gets_the_area_right_which_is_why_it_lasted():
    """`clip_polygon` keeps its old behaviour: `area_within` and the linter
    want an area, and the bridge does not cost them one."""
    one = clip_polygon([Vec2(*p) for p in U], edges_of(ACROSS_THE_ARMS))
    rings = clip_rings([[Vec2(*p) for p in U]], edges_of(ACROSS_THE_ARMS))

    assert len(one) == 8
    assert polygon_area(one) == pytest.approx(24.0)
    assert sum(abs(polygon_area(r)) for r in rings) == \
        pytest.approx(24.0)


def test_a_hole_the_cut_opens_merges_into_the_outline():
    """An outer ring and its hole are cut together, so a region that runs
    through the hole leaves one C, not a ring plus a stray."""
    outer = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)]
    hole = [Vec2(3, 3), Vec2(3, 7), Vec2(7, 7), Vec2(7, 3)]     # wound the other way

    rings = clip_rings([outer, hole], edges_of(Rect(-1, -1, 11, 5)))

    assert len(rings) == 1
    assert polygon_area(rings[0]) == pytest.approx(10 * 5 - 4 * 2)


def test_a_hole_the_cut_misses_stays_a_hole():
    outer = [Vec2(0, 0), Vec2(10, 0), Vec2(10, 10), Vec2(0, 10)]
    hole = [Vec2(3, 3), Vec2(3, 7), Vec2(7, 7), Vec2(7, 3)]

    rings = clip_rings([outer, hole], edges_of(Rect(-1, -1, 11, 11)))

    assert len(rings) == 2
    assert [round(_signed_area(r), 6) for r in rings] == [100.0, -16.0]


def test_a_ring_wholly_outside_leaves_nothing():
    assert clip_rings([[Vec2(*p) for p in U]], edges_of(Rect(20, 20, 30, 30))) == []


def test_winding_is_restored_so_the_hole_is_still_a_hole():
    """Clipping normalises the subject to positive winding and puts it back;
    a shape drawn the other way round comes out drawn the other way round."""
    outer = [Vec2(0, 10), Vec2(10, 10), Vec2(10, 0), Vec2(0, 0)]       # negative
    hole = [Vec2(3, 3), Vec2(7, 3), Vec2(7, 7), Vec2(3, 7)]            # positive
    node = Diagram(prim=PathPrim(
        (Subpath(tuple(outer), True), Subpath(tuple(hole), True)), filled=True))

    cut = inklet.clip(node, Rect(-1, -1, 11, 11))
    areas = [round(_signed_area([Vec2(*p) for p in ring]), 6)
             for ring in world_points(cut)]
    assert areas == [-100.0, 16.0]


def test_the_open_pieces_of_a_path_are_still_cut_as_chains():
    """A filled ring and an open chain in the same path go their own ways."""
    node = Diagram(prim=PathPrim((
        Subpath(tuple(Vec2(*p) for p in U), True),
        Subpath((Vec2(-5, 6), Vec2(15, 6)), False),
    ), filled=True))

    pieces = world_points(inklet.clip(node, ACROSS_THE_ARMS))

    assert len(pieces) == 3
    assert pieces[-1] == [(-1.0, 6.0), (11.0, 6.0)]


def test_cutting_rings_matches_the_area_sutherland_hodgman_computes():
    """A property, over shapes concave enough to split: the pieces are the
    same fill, and none of them is a degenerate sliver."""
    import math
    import random

    random.seed(7)
    for _ in range(400):
        n = random.randint(4, 12)
        ring = [Vec2(math.cos(2 * math.pi * i / n) * random.uniform(2, 10),
                     math.sin(2 * math.pi * i / n) * random.uniform(2, 10))
                for i in range(n)]
        if _signed_area(ring) < 0.0:
            ring.reverse()
        x0, y0 = random.uniform(-8, 0), random.uniform(-8, 0)
        edges = edges_of(Rect(x0, y0, x0 + random.uniform(1, 16),
                              y0 + random.uniform(1, 16)))
        pieces = clip_rings([ring], edges)
        reference = clip_polygon(ring, edges)
        expected = _signed_area(reference) if len(reference) >= 3 else 0.0
        assert sum(_signed_area(p) for p in pieces) == pytest.approx(expected)
        assert all(abs(_signed_area(p)) > 1e-9 for p in pieces)


def _prims(node: Diagram) -> list[PathPrim]:
    return [child.prim for child in node.walk()
            if isinstance(child.prim, PathPrim)]


def test_a_clip_keeps_the_fill_rule_the_path_declared():
    """`fill_rule` (core M14) is part of what a path *means*: the same two
    rings are an annulus under evenodd and a disc under nonzero. The clip
    rebuilds the prim, so it has to carry the rule with it or a cut annulus
    comes back filled solid."""
    outer = Subpath(tuple(Vec2(x, y) for x, y in
                          [(-8, -8), (8, -8), (8, 8), (-8, 8)]), True)
    inner = Subpath(tuple(Vec2(x, y) for x, y in
                          [(-4, -4), (4, -4), (4, 4), (-4, 4)]), True)
    node = Diagram(prim=PathPrim((outer, inner), filled=True,
                                 fill_rule="evenodd"))

    cut = inklet.clip(node, Rect(-6.0, -20.0, 20.0, 20.0))

    assert [p.fill_rule for p in _prims(cut)] == ["evenodd"]


def test_an_uncut_path_keeps_its_fill_rule_too():
    """The untouched case returns the same object, so this is really a guard
    against a future "always rebuild" shortcut losing the rule."""
    ring = Subpath(tuple(Vec2(x, y) for x, y in
                         [(0, 0), (4, 0), (4, 4), (0, 4)]), True)
    node = Diagram(prim=PathPrim((ring,), filled=True, fill_rule="evenodd"))
    assert [p.fill_rule for p in _prims(inklet.clip(node, BOX))] == ["evenodd"]


def test_the_default_rule_is_still_nonzero_after_a_cut():
    ring = Subpath(tuple(Vec2(x, y) for x, y in
                         [(-2, -2), (12, -2), (12, 12), (-2, 12)]), True)
    node = Diagram(prim=PathPrim((ring,), filled=True))
    assert [p.fill_rule for p in _prims(inklet.clip(node, BOX))] == ["nonzero"]
