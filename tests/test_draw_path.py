"""inklet.draw: paths, curves, and the centring convention.

The assertions are geometric rather than structural. A path that renders is not
the same as a path whose flattening agrees with its cubics, and the
disagreement does not show up here -- it shows up two modules downstream as an
arrow that misses its target by a millimetre.
"""

from __future__ import annotations

import math
import subprocess
import sys

import pytest

import inklet
from inklet.core import PathPrim, Vec2, mm, pt
from inklet.draw import (
    ORIGIN_ANCHOR, as_drawn, catmull_rom, curve, path, polygon, polyline,
)
from inklet.draw.path import EPS, bezier

SQUARE = ((0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0))
DIAMOND = ((0.0, -5.0), (5.0, 0.0), (0.0, 5.0), (-5.0, 0.0))


def subpath(node):
    prim = node.prim
    assert isinstance(prim, PathPrim)
    assert len(prim.subpaths) == 1
    return prim.subpaths[0]


def directions(count: int = 32):
    for i in range(count):
        angle = 2 * math.pi * i / count
        yield Vec2(math.cos(angle), math.sin(angle))


# --- points ------------------------------------------------------------------


def test_a_point_may_be_a_pair_a_vec2_or_a_length() -> None:
    """One geometry, three ways of writing it -- units included."""
    plain = polyline(((0.0, 0.0), (10.0, 5.0)))
    vectors = polyline((Vec2(0.0, 0.0), Vec2(10.0, 5.0)))
    written = polyline((("0mm", "0mm"), ("10mm", "5mm")))
    assert subpath(plain).points == subpath(vectors).points
    assert subpath(plain).points == subpath(written).points
    # ...and a point may mix them, since every component goes through mm().
    assert subpath(polyline(((0, 0), (mm("10mm"), pt(0))))).points[1].x == 5.0


def test_a_string_is_not_a_point() -> None:
    with pytest.raises(TypeError, match="not the string"):
        polyline(["ab", (1.0, 2.0)])


def test_a_path_needs_a_point() -> None:
    with pytest.raises(ValueError, match="at least one point"):
        path(())


# --- centring ----------------------------------------------------------------


def test_geometry_is_centred_on_the_local_origin() -> None:
    """The convention core uses for `RectPrim`, kept by everything drawn."""
    node = polyline(SQUARE, closed=True)
    box = node.bbox
    assert box.center.x == pytest.approx(0.0)
    assert box.center.y == pytest.approx(0.0)
    assert (box.width, box.height) == pytest.approx((10.0, 6.0))


def test_a_path_stacks_like_any_other_shape() -> None:
    """Centred geometry is what makes this true: two paths of the same size
    land on top of each other, wherever their authors put them."""
    here = polyline(SQUARE, closed=True)
    there = polyline([(x + 100.0, y - 40.0) for x, y in SQUARE], closed=True)
    assert here.bbox.center == there.bbox.center


def test_as_drawn_restores_the_authored_coordinates() -> None:
    node = as_drawn(polyline(SQUARE, closed=True))
    box = node.bbox
    assert (box.x0, box.y0, box.x1, box.y1) == pytest.approx((0.0, 0.0, 10.0, 6.0))


def test_the_origin_anchor_records_where_zero_went() -> None:
    node = polyline(SQUARE, closed=True)
    at = node.anchor_point(ORIGIN_ANCHOR)
    assert (at.x, at.y) == pytest.approx((-5.0, -3.0))


# --- envelopes ---------------------------------------------------------------


def test_polygon_envelope_is_the_convex_extent_not_a_bounding_box() -> None:
    """The support function in every direction, checked against the points it
    was built from. A bbox implementation passes on the axes and fails on the
    diagonals, which is exactly where tight packing happens."""
    node = polygon(DIAMOND)
    points = [Vec2(x, y) for x, y in DIAMOND]
    for direction in directions():
        expected = max(direction.dot(p) for p in points)
        assert node.envelope.extent(direction) == pytest.approx(expected, abs=1e-9)


def test_the_diagonal_extent_is_tighter_than_a_box() -> None:
    node = polygon(DIAMOND)
    diagonal = Vec2(1.0, 1.0).normalized()
    assert node.envelope.extent(diagonal) == pytest.approx(5.0 / math.sqrt(2.0))
    assert node.envelope.extent(Vec2(1.0, 0.0)) == pytest.approx(5.0)


# --- curves ------------------------------------------------------------------


CONTROL = ((0.0, 0.0), (10.0, -8.0), (20.0, 4.0), (30.0, -2.0), (40.0, 0.0))


def test_a_curve_passes_exactly_through_every_control_point() -> None:
    """Catmull-Rom's whole reason for being. Exactly, not nearly: a bezier is
    exact at t=0 and t=1, so the knots survive flattening untouched."""
    node = curve(CONTROL)
    # The geometry was shifted onto the origin; the anchor says by how much, so
    # this reads the flattening back in the coordinates the caller wrote.
    origin = node.anchor_point(ORIGIN_ANCHOR)
    world = [p - origin for p in subpath(node).points]
    for x, y in CONTROL:
        assert min((p - Vec2(x, y)).length for p in world) < 1e-9


def test_the_cubic_chain_covers_the_whole_path() -> None:
    """`Subpath.curves`, when present, is what the SVG backend draws; a chain
    that skips a segment silently loses it."""
    sub = subpath(curve(CONTROL))
    assert sub.curves
    assert (sub.curves[0][0] - sub.points[0]).length < EPS
    assert (sub.curves[-1][3] - sub.points[-1]).length < EPS
    for before, after in zip(sub.curves, sub.curves[1:]):
        assert (before[3] - after[0]).length < EPS


def test_the_flattening_agrees_with_the_cubics() -> None:
    """Core measures from `points` and the backend draws `curves`; if they
    disagree, an envelope is a lie about what is on the page."""
    sub = subpath(curve(CONTROL, smooth=0.7))
    for cubic in sub.curves:
        for i in range(1, 8):
            at = bezier(*cubic, i / 8)
            assert min((at - p).length for p in sub.points) < 0.02


def test_smooth_zero_reproduces_the_polyline() -> None:
    straight = subpath(polyline(CONTROL)).points
    flat = subpath(curve(CONTROL, smooth=0.0)).points
    for point in straight:
        assert min((point - p).length for p in flat) < 1e-9


def test_a_closed_curve_wraps_around() -> None:
    node = curve(DIAMOND, closed=True)
    sub = subpath(node)
    assert sub.closed
    assert len(sub.curves) == len(DIAMOND)     # one per edge, including the last
    assert (sub.curves[-1][3] - sub.curves[0][0]).length < EPS


def test_catmull_rom_ends_do_not_bend_outward() -> None:
    """An open curve has no neighbour past its ends. Standing the end point in
    for the missing one keeps the first control point on the chord."""
    chain = catmull_rom([Vec2(0, 0), Vec2(10, 0), Vec2(20, 0)], 0.5)
    assert chain[0][1].y == pytest.approx(0.0)


def test_a_curve_needs_two_points() -> None:
    with pytest.raises(ValueError, match="at least two points"):
        curve([(0.0, 0.0)])


def test_negative_smoothing_is_refused() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        curve(CONTROL, smooth=-0.2)


# --- the curves contract -----------------------------------------------------


def test_a_chain_that_stops_short_is_refused() -> None:
    short = ((Vec2(0, 0), Vec2(3, 0), Vec2(7, 0), Vec2(10, 0)),)
    with pytest.raises(ValueError, match="cover the whole path"):
        path([(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)], curves=short)


def test_a_broken_chain_is_refused() -> None:
    broken = (
        (Vec2(0, 0), Vec2(3, 0), Vec2(7, 0), Vec2(10, 0)),
        (Vec2(11, 0), Vec2(13, 0), Vec2(17, 0), Vec2(20, 0)),
    )
    with pytest.raises(ValueError, match="contiguous"):
        path(curves=broken)


def test_a_cubic_has_four_points() -> None:
    with pytest.raises(ValueError, match="is \\(start, control, control, end\\)"):
        path(curves=((Vec2(0, 0), Vec2(1, 1), Vec2(2, 2)),))


# --- fill --------------------------------------------------------------------


def test_a_fill_implies_a_filled_path() -> None:
    assert path(SQUARE, closed=True, fill="#eeeeee").prim.filled
    assert not path(SQUARE, closed=True).prim.filled
    assert not path(SQUARE, closed=True, fill="none").prim.filled


def test_polygon_is_closed_and_fillable() -> None:
    node = polygon(SQUARE)
    assert subpath(node).closed
    assert node.prim.filled


# --- determinism -------------------------------------------------------------


PROBE = """
import inklet
fig = inklet.figure(width="60mm")
fig.add(inklet.hstack([
    inklet.curve([(0, 0), (10, -8), (20, 4), (30, -2)]),
    inklet.polygon([(0, 0), (10, 0), (10, 6), (0, 6)]),
    inklet.marker("star"),
    inklet.arc(8, 0, 210),
]))
print(fig.to_svg())
"""


@pytest.mark.parametrize("seed", ["0", "12345"])
def test_the_svg_does_not_depend_on_the_hash_seed(seed: str, tmp_path) -> None:
    """Byte-identical output across processes is a contract, and dict and set
    iteration is where it usually dies."""
    script = tmp_path / "probe.py"
    script.write_text(PROBE)
    env = {"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"}
    out = subprocess.run([sys.executable, str(script)], capture_output=True,
                         check=True, env=env)
    reference = subprocess.run([sys.executable, str(script)], capture_output=True,
                               check=True, env={**env, "PYTHONHASHSEED": "0"})
    assert out.stdout == reference.stdout


# -- fill_rule, reachable from the public API --------------------------------

WASHER_OUT = [(-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0)]
#: Wound the *same* way as the outer ring on purpose: under nonzero that is a
#: solid square, and the hole only appears because the rule says evenodd.
WASHER_IN = [(-4.0, -4.0), (4.0, -4.0), (4.0, 4.0), (-4.0, 4.0)]


def washer(**kwargs):
    return inklet.polygon(WASHER_OUT, holes=[WASHER_IN], fill="#cccccc", **kwargs)


def test_a_washer_is_one_prim_with_two_rings():
    """Two rings on one prim, not two shapes lying on each other: a washer
    clips as one object and a ray leaves it through the outside."""
    prim = washer(fill_rule="evenodd").prim
    assert isinstance(prim, PathPrim)
    assert len(prim.subpaths) == 2
    assert all(sub.closed for sub in prim.subpaths)


def test_the_public_api_can_ask_for_evenodd():
    """`fill_rule` is geometry, not paint, so it belongs on the prim -- but it
    used to reach `Style.__init__` through `**style` and raise there, with no
    hint that the field existed."""
    assert washer(fill_rule="evenodd").prim.fill_rule == "evenodd"
    assert washer().prim.fill_rule == "nonzero"


def test_evenodd_reaches_the_svg():
    fig = inklet.figure(width="40mm")
    fig.add(washer(fill_rule="evenodd"))
    assert 'fill-rule="evenodd"' in fig.to_svg()


def test_the_default_writes_no_fill_rule_at_all():
    """Nonzero is the SVG default, so saying it is noise in the file."""
    fig = inklet.figure(width="40mm")
    fig.add(washer())
    assert "fill-rule" not in fig.to_svg()


def test_evenodd_reaches_the_pdf():
    """The starred painting operators are the whole of the rule on that side."""
    fig = inklet.figure(width="40mm")
    fig.add(washer(fill_rule="evenodd"))
    assert b"B*" in fig.to_pdf(compress=False)


def test_polyline_and_path_take_it_too():
    assert inklet.polyline([(0.0, 0.0), (5.0, 5.0)],
                        fill_rule="evenodd").prim.fill_rule == "evenodd"
    assert inklet.path(WASHER_OUT, closed=True,
                    fill_rule="evenodd").prim.fill_rule == "evenodd"


def test_a_bad_rule_is_refused_by_the_prim():
    with pytest.raises(ValueError, match="fill_rule"):
        washer(fill_rule="winding")


def test_a_hole_needs_a_ring():
    with pytest.raises(ValueError, match="at least three points"):
        inklet.polygon(WASHER_OUT, holes=[[(0.0, 0.0), (1.0, 1.0)]])


def test_holes_are_inside_the_shape_the_bbox_reports():
    """The hole must not move the frame: a washer is as big as its outside."""
    assert washer(fill_rule="evenodd").bbox == inklet.polygon(WASHER_OUT).bbox
