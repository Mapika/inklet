"""inklet.plot.ecdf and Panel.ecdf: the steps, and the staircase drawn from them."""

from __future__ import annotations

import math

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.plot import ecdf, panel
from inklet.plot.cumulative import staircase


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def test_ties_share_a_step() -> None:
    assert ecdf([3, 1, 2, 2]) == ((1.0, 2.0, 3.0), (0.25, 0.75, 1.0))


def test_missing_values_are_left_out_of_the_denominator() -> None:
    assert ecdf([1, None, float("nan"), 2]) == ((1.0, 2.0), (0.5, 1.0))


def test_complementary_is_the_share_strictly_above() -> None:
    xs, ys = ecdf([1, 2, 2, 3], complementary=True)
    assert ys == (0.75, 0.25, 0.0)


def test_weights_and_counts() -> None:
    assert ecdf([1, 2], weights=[3, 1]) == ((1.0, 2.0), (0.75, 1.0))
    assert ecdf([1, 2, 2], normalize=False) == ((1.0, 2.0), (1.0, 3.0))
    with pytest.raises(DiagramError):
        ecdf([1, 2], weights=[1, -1])
    with pytest.raises(DiagramError):
        ecdf([None])


def test_staircase_is_post_step_and_extends() -> None:
    points = staircase((1.0, 2.0), (0.5, 1.0), start=0.0, low=0.0, high=3.0)
    assert points == [(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (2.0, 0.5),
                      (2.0, 1.0), (3.0, 1.0)]


def line_points(p):
    """The page vertices of the one drawn line."""
    for placed in resolve(as_drawn(p.build())).values():
        prim = placed.diagram.prim
        if placed.diagram.kind == "path" and hasattr(prim, "subpaths"):
            return [placed.world.apply(v) for v in prim.subpaths[0].points]
    raise AssertionError("no line")


def test_panel_ecdf_runs_across_the_axis() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 1))
    p.ecdf([2, 4, 6, 8], name="a")
    pts = line_points(p)
    assert math.isclose(pts[0].x, p.point(0, 0).x, abs_tol=1e-6)
    assert math.isclose(pts[-1].x, p.point(10, 1).x, abs_tol=1e-6)
    assert math.isclose(pts[-1].y, p.point(10, 1).y, abs_tol=1e-6)
    assert [k.name for k in p.keys] == ["a"]
    assert "line" in p.keys[0].forms


def test_panel_ecdf_drops_zero_on_a_log_axis() -> None:
    p = panel(40, 30, x=(0, 10), y=inklet.plot.log((0.01, 1)))
    p.ecdf([1, 2, 3, 4], complementary=True)
    pts = line_points(p)
    assert all(math.isfinite(v.y) for v in pts)
    assert min(v.y for v in pts) >= p.point(0, 1).y - 1e-6


def test_ecdf_lints_clean_and_exports() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 1))
    p.ecdf([1, 3, 3, 5, 7], name="a").ecdf([2, 4, 8], name="b").axes()
    node = p.build()
    assert lint(node) == []
    assert inklet.to_pdf(node)[:4] == b"%PDF"
    assert "<path" in inklet.to_svg(node)
