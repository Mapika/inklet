"""Panel.dumbbell and Panel.lollipop: dots on connectors, read back from the page."""

from __future__ import annotations

import math

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import panel


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def placed(p, kind):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == kind]


def test_dumbbell_dots_land_on_values_and_share_the_category_line() -> None:
    p = panel(40, 30, x=(0, 10), y=["a", "b"])
    p.dumbbell(["a", "b"], [[2, 3], [8, 3]], orient="h")
    dots = placed(p, MARK_KIND)
    assert len(dots) == 4
    xs = sorted(round(d.bbox.center.x, 6) for d in dots)
    expected = sorted(round(p.point(v, "a").x, 6) for v in (2, 3, 8, 3))
    assert xs == expected
    # One connector: category b has two equal values and no length to draw.
    lines = placed(p, MARK_LINE_KIND)
    assert len(lines) == 1
    line = lines[0].bbox
    assert math.isclose(line.x0, p.point(2, "a").x, abs_tol=1e-6)
    assert math.isclose(line.x1, p.point(8, "a").x, abs_tol=1e-6)
    assert math.isclose(line.center.y, p.point(0, "a").y, abs_tol=1e-6)


def test_dumbbell_missing_value_draws_one_dot_and_no_line() -> None:
    p = panel(40, 30, x=["a"], y=(0, 10))
    p.dumbbell(["a"], [[None], [4]])
    assert len(placed(p, MARK_KIND)) == 1
    assert placed(p, MARK_LINE_KIND) == []


def test_dumbbell_legend_has_one_marker_per_name() -> None:
    p = panel(40, 30, x=["a", "b"], y=(0, 10))
    p.dumbbell(["a", "b"], [[1, 2], [3, 4]], names=["pre", "post"])
    keys = p.keys
    assert [k.name for k in keys] == ["pre", "post"]
    assert all("marker" in k.forms for k in keys)
    assert keys[0].color != keys[1].color
    with pytest.raises(DiagramError):
        p.dumbbell(["a", "b"], [[1, 2], [3, 4]], names=["only one"])


def test_dumbbell_needs_two_series() -> None:
    p = panel(40, 30, x=["a"], y=(0, 10))
    with pytest.raises(DiagramError):
        p.dumbbell(["a"], [3])


def test_lollipop_stem_runs_from_baseline_to_dot() -> None:
    p = panel(40, 30, x=["a", "b", "c"], y=(-5, 5))
    p.lollipop(["a", "b", "c"], [3, -2, None], name="score")
    stems = placed(p, MARK_LINE_KIND)
    dots = placed(p, MARK_KIND)
    assert len(stems) == 2 and len(dots) == 2
    zero = p.point("a", 0).y
    for stem in stems:
        assert math.isclose(min(abs(stem.bbox.y0 - zero), abs(stem.bbox.y1 - zero)),
                            0, abs_tol=1e-6)
    assert [k.name for k in p.keys] == ["score"]


def test_paired_marks_lint_clean_and_export() -> None:
    p = panel(40, 30, x=["a", "b", "c"], y=(0, 10))
    p.dumbbell(["a", "b", "c"], [[1, 4, 6], [3, 5, 9]]).axes()
    q = panel(40, 30, x=["a", "b", "c"], y=(0, 10))
    q.lollipop(["a", "b", "c"], [2, 7, 5]).axes()
    for node in (p.build(), q.build()):
        assert lint(node) == []
        assert inklet.to_svg(node).startswith("<")
        assert inklet.to_pdf(node)[:4] == b"%PDF"
