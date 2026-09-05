"""inklet.draw: arcs, wedges, markers and explicit placement."""

from __future__ import annotations

import math

import pytest

from inklet.core import Diagram, EllipsePrim, PathPrim, RectPrim, Vec2
from inklet.draw import (
    MARKER_KINDS, ORIGIN_ANCHOR, arc, arc_cubics, as_drawn, marker, place,
    sector,
)
from inklet.draw.path import bezier
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND

AREA_MARKERS = ("circle", "square", "triangle", "diamond", "star")


def area_of(prim) -> float:
    """The ink a marker lays down, from whatever primitive it turned into."""
    if isinstance(prim, EllipsePrim):
        return math.pi * prim.rx * prim.ry
    if isinstance(prim, RectPrim):
        return prim.width * prim.height
    points = prim.subpaths[0].points
    total = 0.0
    for a, b in zip(points, points[1:] + points[:1]):
        total += a.x * b.y - b.x * a.y
    return abs(total) / 2


def authored(node: Diagram) -> Vec2:
    """Where the author's (0, 0) ended up in the node's own frame."""
    return node.anchor_point(ORIGIN_ANCHOR)


# --- arcs --------------------------------------------------------------------


def test_an_arc_lies_on_its_circle() -> None:
    """Sampled off the cubics, not off the flattening: the cubics are what the
    backend draws, so they are what has to be round."""
    for cubic in arc_cubics(Vec2(0.0, 0.0), 10.0, 0.0, 270.0):
        for i in range(9):
            at = bezier(*cubic, i / 8)
            assert at.length == pytest.approx(10.0, abs=0.005)


def test_an_arc_spans_the_angles_it_was_given() -> None:
    node = as_drawn(arc(10.0, 0.0, 90.0))
    box = node.bbox
    # 0 deg is east and angles run clockwise on the page, where y grows down.
    assert (box.x0, box.y0) == pytest.approx((0.0, 0.0), abs=1e-9)
    assert (box.x1, box.y1) == pytest.approx((10.0, 10.0), abs=1e-9)


def test_a_full_circle_closes() -> None:
    node = arc(6.0, 0.0, 360.0, closed=True)
    box = node.bbox
    assert (box.width, box.height) == pytest.approx((12.0, 12.0), abs=1e-3)


def test_a_sector_reaches_its_own_centre() -> None:
    """A wedge is a pie slice: the point at the middle of the circle is part of
    the shape, which is what makes `place()` land it by that centre."""
    node = as_drawn(sector(10.0, 0.0, 90.0))
    box = node.bbox
    assert (box.x0, box.y0) == pytest.approx((0.0, 0.0), abs=1e-9)


def test_an_annular_sector_leaves_its_middle_out() -> None:
    node = sector(10.0, 0.0, 90.0, inner=6.0)
    # Read back in the coordinates it was drawn in: the circle centre is where
    # the author's (0, 0) went, and nothing may come nearer to it than `inner`.
    origin = authored(node)
    radii = [(p - origin).length for p in node.prim.subpaths[0].points]
    assert min(radii) == pytest.approx(6.0, abs=0.005)
    assert max(radii) == pytest.approx(10.0, abs=0.005)


def test_the_origin_of_a_sector_is_the_centre_of_its_circle() -> None:
    node = sector(10.0, 0.0, 90.0)
    at = authored(node)
    assert (at.x, at.y) == pytest.approx((-node.bbox.width / 2, -node.bbox.height / 2))


# --- markers -----------------------------------------------------------------


@pytest.mark.parametrize("kind", AREA_MARKERS)
def test_area_markers_carry_the_same_ink(kind: str) -> None:
    """A square drawn to the same box as a circle is 27% heavier. Equal area is
    what lets one series swap glyph without changing weight."""
    node = marker(kind, 4.0)
    assert area_of(node.prim) == pytest.approx(math.pi * 4.0, rel=0.01)


@pytest.mark.parametrize("kind", MARKER_KINDS)
def test_every_marker_is_centred_on_the_point_it_stands_for(kind: str) -> None:
    node = marker(kind, 4.0)
    box = node.bbox
    assert (box.center.x, box.center.y) == pytest.approx((0.0, 0.0), abs=1e-9)
    assert (authored(node).x, authored(node).y) == (0.0, 0.0)


@pytest.mark.parametrize("kind", ("cross", "plus"))
def test_line_markers_are_not_filled(kind: str) -> None:
    """They are strokes. Themed as an area they would disappear."""
    node = marker(kind, 4.0)
    assert isinstance(node.prim, PathPrim) and not node.prim.filled
    assert node.kind == MARK_LINE_KIND


@pytest.mark.parametrize("kind", AREA_MARKERS)
def test_area_markers_are_filled(kind: str) -> None:
    assert marker(kind, 4.0).kind == MARK_KIND


def test_marker_size_defaults_to_the_type_size() -> None:
    import inklet

    size = marker("circle").bbox.width
    assert 0.4 * inklet.current_theme().font_size < size < inklet.current_theme().font_size


def test_an_unknown_marker_says_what_it_knows() -> None:
    with pytest.raises(ValueError, match="unknown marker 'blob'"):
        marker("blob")


def test_a_marker_needs_a_positive_size() -> None:
    with pytest.raises(ValueError, match="positive size"):
        marker("circle", 0.0)


# --- place -------------------------------------------------------------------


def test_place_puts_a_child_on_its_point() -> None:
    points = ((0.0, 0.0), (20.0, -10.0), (40.0, 6.0))
    node = as_drawn(place([(p, marker("circle", 2.0)) for p in points]))
    for child, (x, y) in zip(node.children, points):
        at = child.transform.apply(child.anchor_point("center"))
        assert (at.x, at.y) == pytest.approx((x, y), abs=1e-9)


def test_place_puts_a_drawn_child_back_where_it_was_drawn() -> None:
    """A path and the markers riding on it, in one call."""
    track = ((0.0, 0.0), (20.0, -10.0), (40.0, 6.0))
    from inklet.draw import polyline

    node = as_drawn(place([polyline(track)] + [(p, marker("circle", 2.0))
                                              for p in track]))
    box = node.bbox
    assert (box.x0, box.y0) == pytest.approx((-1.0, -11.0), abs=1e-9)
    assert (box.x1, box.y1) == pytest.approx((41.0, 7.0), abs=1e-9)


def test_place_refuses_the_same_diagram_twice() -> None:
    """The rule core enforces at resolve time, said earlier and more clearly."""
    once = marker("circle", 2.0)
    with pytest.raises(ValueError, match="use .copy()"):
        place([((0.0, 0.0), once), ((10.0, 0.0), once)])


def test_place_rejects_something_that_is_not_a_diagram() -> None:
    with pytest.raises(TypeError, match="pairs a point with a str"):
        place([((0.0, 0.0), "not a diagram")])
