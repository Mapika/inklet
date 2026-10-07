"""KEY_COVERS_DATA: a key set inside the plot on top of the panel's data.

The repros are the two from ISSUES-physics 1: a 40-cycle sine under a
`corner="sw"` legend, and a single point under a `corner="nw"` key. Both used
to lint clean while the PNG showed the data cut out.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

import inklet as i


def found(figure, code="KEY_COVERS_DATA"):
    return [d for d in figure.lint() if d.code == code]


def _compiled(spec, width=100):
    doc = i.document(width=width)
    doc.add("a", spec)
    return doc.compile()


def _sine(corner=None, side=None, y=(-1, 1)):
    t = np.linspace(0, 1, 400)
    p = i.plot_spec(80, 20, x=(0, 1), y=y, clip=True)
    p.line(np.c_[t, np.sin(40 * t)], name="Residual")
    p.axes()
    if side is not None:
        p.legend(side=side)
    else:
        p.legend(corner=corner)
    return _compiled(p)


def _point(corner):
    q = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
    q.scatter([(0.15, 0.9), (0.5, 0.5)], name="points").axes()
    q.legend(corner=corner, entries=[("a long hand-written key entry", "#333333")])
    return _compiled(q)


def test_a_legend_plate_over_a_line_is_a_warning_naming_the_series():
    (finding,) = found(_sine(corner="sw"))
    assert finding.severity == "warning"
    assert "legend" in finding.message and "sw corner" in finding.message
    assert "'Residual'" in finding.message
    # How much of the line is gone, in millimetres.
    assert "mm of line" in finding.message
    assert "corner='auto'" in finding.hint and "side=" in finding.hint
    assert "y range downward" in finding.hint


def test_a_legend_plate_over_a_point_names_its_data_position_and_clear_corners():
    (finding,) = found(_point("nw"))
    assert "1 marker (at x=0.15, y=0.9)" in finding.message
    assert "hides data" in finding.message
    # The other three corners are empty in this plot, and the hint says so.
    assert "corner='ne', 'se' or 'sw'" in finding.hint


def test_targets_name_the_key_and_the_covered_mark():
    figure = _point("nw")
    (finding,) = found(figure)
    root, _ = figure.build()
    kinds = {node.id: node.kind for node in root.walk()}
    assert any(kinds[t] == "mark" for t in finding.targets)
    assert finding.where is not None


@pytest.mark.parametrize("corner", ["ne", "se"])
def test_a_key_in_an_empty_corner_is_silent(corner):
    assert found(_point(corner)) == []


def test_a_key_placed_by_clear_space_search_is_silent():
    assert found(_point("auto")) == []
    assert found(_point("best")) == []
    assert found(_sine(corner="best")) == []


def test_a_key_outside_the_plot_is_silent():
    assert found(_sine(side="right")) == []
    assert found(_sine(side="top")) == []


def test_widening_the_range_clears_it():
    assert found(_sine(corner="nw", y=(-1, 2.2))) == []


def test_marks_drawn_after_the_key_are_on_top_and_not_hidden():
    p = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
    p.axes()
    p.legend(corner="nw", entries=[("key", "#333333")])
    p.scatter([(0.05, 0.95)])
    assert found(_compiled(p)) == []


def test_a_bar_whose_top_runs_under_the_key_is_reported():
    entries = [("a fairly long legend entry", "#333333")]
    p = i.plot_spec(80, 40, x=(0.5, 3.5), y=(0, 10))
    p.bars([1, 2, 3], [3, 5, 9.5]).axes().legend(corner="ne", entries=entries)
    (finding,) = found(_compiled(p))
    assert "of the outline of" in finding.message
    assert "corner='nw'" in finding.hint

    q = i.plot_spec(80, 40, x=(0.5, 3.5), y=(0, 10))
    q.bars([1, 2, 3], [3, 5, 6]).axes().legend(corner="ne", entries=entries)
    assert found(_compiled(q)) == []


def test_a_size_key_in_a_corner_over_a_bubble_is_reported_and_auto_is_not():
    scale = i.plot.area_scale(1e9, 6)

    def build(corner):
        p = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
        p.scatter([(0.1, 0.9), (0.5, 0.5)], size=2).axes()
        p.size_key(scale, values=[1e7, 1e9], corner=corner)
        return _compiled(p)

    (finding,) = found(build("nw"))
    assert finding.message.startswith("the size key in the nw corner")
    assert found(build("auto")) == []


def test_a_colorbar_inset_over_a_matrix_is_not_judged():
    p = i.plot_spec(40, 40, x=(0, 10), y=(0, 10))
    p.matrix(np.arange(100).reshape(10, 10), ramp="viridis")
    p.colorbar(corner="ne", length=10)
    assert found(_compiled(p)) == []


def test_the_rule_is_registered_and_runs_alone():
    from inklet.diagnostics import RULES
    assert "KEY_COVERS_DATA" in RULES
    figure = _point("nw")
    root, placements = figure.build()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        diags = i.lint(root, page=root.bbox, placements=placements,
                       rules=["KEY_COVERS_DATA"])
    assert [d.code for d in diags] == ["KEY_COVERS_DATA"]


def test_length_in_box_is_exact_for_a_crossing_segment():
    from inklet.core import Rect, Vec2
    from inklet.diagnostics.key_cover import _length_in
    box = Rect(0, 0, 10, 10)
    assert _length_in(Vec2(-5, 5), Vec2(15, 5), box) == pytest.approx(10.0)
    assert _length_in(Vec2(5, -5), Vec2(5, 15), box) == pytest.approx(10.0)
    assert _length_in(Vec2(-5, -5), Vec2(-1, 20), box) == 0.0
    assert _length_in(Vec2(2, 2), Vec2(4, 2), box) == pytest.approx(2.0)
