"""PolarPanel.radar, radar_grid and pie."""

from __future__ import annotations

import math

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import active_theme, as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import polar
from inklet.plot.axis import TICK_LABEL_KIND
from inklet.plot.furniture import GRID_KIND
from inklet.plot.wheel import pie_label_texts, radar_spokes


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def placements(p, kind):
    return [x for x in resolve(as_drawn(p.build())).values()
            if x.diagram.kind == kind]


def texts(p, kind=TICK_LABEL_KIND):
    return {x.diagram.prim.text: x for x in placements(p, kind)
            if getattr(x.diagram.prim, "text", None)}


def test_spokes_divide_the_turn_evenly() -> None:
    p = polar(20, r=(0, 1))
    assert radar_spokes(p, 4) == (0.0, 90.0, 180.0, 270.0)
    with pytest.raises(DiagramError):
        radar_spokes(p, 2)


def test_radar_vertices_sit_on_their_spokes() -> None:
    p = polar(20, r=(0, 1), zero="up", winding="cw")
    p.radar([1.0, 0.5, 1.0, 0.5], name="a", fill=False, markers=False)
    line, = placements(p, MARK_LINE_KIND)
    pts = [line.world.apply(v) for v in line.diagram.prim.subpaths[0].points]
    assert math.isclose(pts[0].x, 0, abs_tol=1e-6)
    assert math.isclose(pts[0].y, -20, abs_tol=1e-6)      # up, at the rim
    assert math.isclose(pts[1].x, 10, abs_tol=1e-6)       # clockwise: east
    assert [k.name for k in p.keys] == ["a"]


def test_radar_needs_a_whole_turn() -> None:
    p = polar(20, r=(0, 1), theta=(0, 180))
    with pytest.raises(DiagramError):
        p.radar([1, 2, 3])


def test_radar_grid_draws_rings_spokes_and_names() -> None:
    p = polar(20, r=(0, 1))
    p.radar_grid(["a", "b", "c", "d", "e"], rings=[0.5])
    grid = placements(p, GRID_KIND)
    assert len(grid) == 2 + 5            # ring at 0.5 and the rim, 5 spokes
    names = texts(p)
    assert sorted(names) == ["a", "b", "c", "d", "e"]
    for label in names.values():
        c = label.bbox.center
        assert math.hypot(c.x, c.y) > 20


def test_pie_slices_span_their_shares() -> None:
    p = polar(20, zero="up", winding="cw")
    p.pie([1, 3], labels=None, separator=False)
    wedges = placements(p, MARK_KIND)
    assert len(wedges) == 2
    # The first quarter is the north-east quadrant.
    small = min(wedges, key=lambda w: w.bbox.width * w.bbox.height)
    assert small.bbox.x0 >= -1e-6 and small.bbox.y1 <= 1e-6


def test_pie_labels_go_inside_or_outside_by_fit() -> None:
    p = polar(14, zero="up", winding="cw")
    p.pie([90, 8, 2], names=["big", "mid", "tiny"])
    node = p._content[-1]
    note = node.notes["pie_labels"]
    assert 0 in note["inside"] and 2 in note["outside"]
    labels = texts(p)
    tiny = labels["2%"].bbox.center
    assert math.hypot(tiny.x, tiny.y) > 14
    assert [k.name for k in p.keys] == ["big", "mid", "tiny"]


def test_pie_inside_label_contrasts_with_its_slice() -> None:
    p = polar(14)
    p.pie([1, 1], colors=["#000000", "#ffffff"])
    theme = active_theme()
    fills = {x.style.text_fill for x in placements(p, TICK_LABEL_KIND)
             if getattr(x.diagram.prim, "text", None)}
    assert fills == {theme.ink, theme.paper}


def test_pie_label_spellings() -> None:
    assert pie_label_texts("percent", [1, 3]) == ["25%", "75%"]
    assert pie_label_texts("value", [1, 3]) == ["1", "3"]
    assert pie_label_texts("{share:.1%}", [1, 3]) == ["25.0%", "75.0%"]
    assert pie_label_texts(lambda v, s: f"{v:g}", [1, 3]) == ["1", "3"]
    with pytest.raises(DiagramError):
        pie_label_texts(["a"], [1, 3])


def test_pie_refuses_negative_and_empty() -> None:
    p = polar(14)
    with pytest.raises(DiagramError):
        p.pie([1, -1])
    with pytest.raises(DiagramError):
        p.pie([0, 0])


def test_donut_and_radar_lint_clean_and_export() -> None:
    d = polar(14, hole=7, zero="up", winding="cw")
    d.pie([61, 39])
    r = polar(16, r=(0, 1), zero="up", winding="cw")
    r.radar_grid(["a", "b", "c", "d", "e"])
    r.radar([0.8, 0.6, 0.9, 0.4, 0.7])
    for node in (d.build(), r.build()):
        assert lint(node) == []
        assert inklet.to_pdf(node)[:4] == b"%PDF"
        assert "<path" in inklet.to_svg(node)
