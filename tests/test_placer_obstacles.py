"""Deferred placers keep clear of the reference rules and bands under the data.

`hline`, `vline`, `hspan` and `vspan` paint beneath the data unless `front=True`,
so they are not among the marks a label is placed against unless the placer is
told about them. A label set across an unlabelled dashed rule reads as struck
through, and lint does not report it. `vline(label=)` sets its word at the top
of the rule, which on a histogram is where the tallest bar is.
"""

from __future__ import annotations

import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import resolve
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_KIND, MARK_LINE_KIND
from inklet.plot import panel
from inklet.plot.point_labels import POINT_LABEL_KIND


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def point_label_boxes(p):
    """The boxes of `label_points` labels, keyed by their text."""
    out = {}
    for placed in resolve(as_drawn(p.build())).values():
        prim = placed.diagram.prim
        if placed.diagram.kind == POINT_LABEL_KIND and getattr(prim, "text", None):
            out[prim.text] = placed.bbox
    return out


def strictly_crosses_y(box, y: float) -> bool:
    return box.y0 < y < box.y1


def strictly_crosses_x(box, x: float) -> bool:
    return box.x0 < x < box.x1


def overlaps(a, b) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


def gap_between(a, b) -> float:
    dx = max(a.x0 - b.x1, b.x0 - a.x1, 0.0)
    dy = max(a.y0 - b.y1, b.y0 - a.y1, 0.0)
    return (dx * dx + dy * dy) ** 0.5


# --- label_points against reference lines and bands ------------------------


def test_a_label_points_label_does_not_sit_across_an_unlabelled_hline():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.hline(5.0, stroke_dash=(1.0, 0.8))      # under the data, no label of its own
    pts = [(2.0, 5.0), (5.0, 5.0), (8.0, 5.0)]
    p.scatter(pts)
    p.label_points(pts, ["a", "b", "c"])
    line_y = p.point(0.0, 5.0).y
    boxes = point_label_boxes(p)
    assert set(boxes) == {"a", "b", "c"}
    for name, box in boxes.items():
        assert not strictly_crosses_y(box, line_y), name


def test_a_label_points_label_does_not_straddle_a_band_edge():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.hspan(4.0, 6.0)                          # a shaded band under the data
    pts = [(2.0, 6.0), (5.0, 4.0), (8.0, 6.0)]  # set on its two edges
    p.scatter(pts)
    p.label_points(pts, ["a", "b", "c"])
    boxes = point_label_boxes(p)
    for edge in (p.point(0.0, 4.0).y, p.point(0.0, 6.0).y):
        for name, box in boxes.items():
            assert not strictly_crosses_y(box, edge), name


# --- a histogram's vline word clears its bars -------------------------------


def _histogram_with_mean_rule():
    rng = random.Random(2)
    scores = [rng.gauss(64, 12) for _ in range(1000)]
    mean = sum(scores) / len(scores)
    chart = inklet.hist({"s": scores}, x="s", bins=25)
    chart.vline(mean, label="mean 63.9")
    return chart


def test_a_histogram_vline_label_does_not_intersect_any_bar():
    fig = _histogram_with_mean_rule().compile()
    placed = list(resolve(fig.root).values())
    label = [q.bbox for q in placed
             if getattr(q.diagram.prim, "text", None) == "mean 63.9"]
    bars = [q.bbox for q in placed if q.diagram.kind == MARK_KIND]
    assert len(label) == 1 and len(bars) > 1
    for bar in bars:
        assert not overlaps(label[0], bar)


def test_a_histogram_vline_label_is_not_pressed_against_the_tallest_bar():
    # Two millimetres is the least air a word needs to read as its own; the
    # word was 0.8mm from the nearest bar before the domain made room for it.
    fig = _histogram_with_mean_rule().compile()
    placed = list(resolve(fig.root).values())
    label = [q.bbox for q in placed
             if getattr(q.diagram.prim, "text", None) == "mean 63.9"][0]
    bars = [q.bbox for q in placed if q.diagram.kind == MARK_KIND]
    assert min(gap_between(label, bar) for bar in bars) >= 2.0


# --- label_offset= on a reference rule -------------------------------------


def _rule_and_label(p, text):
    placed = list(resolve(as_drawn(p.build())).values())
    label = [q.bbox for q in placed if getattr(q.diagram.prim, "text", None) == text]
    rule = [q.bbox for q in placed if q.diagram.kind == MARK_LINE_KIND]
    assert len(label) == 1 and len(rule) == 1
    return label[0], (rule[0].x0 + rule[0].x1) / 2


def _bars_and_vline(**kwargs):
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.bars([2.0, 6.0], [5.0, 8.0], width=2.0)
    p.vline(5.0, label="stim", **kwargs)
    return p


def test_label_offset_sets_how_far_the_word_stands_off_the_rule():
    label, rule_x = _rule_and_label(_bars_and_vline(label_offset=4.0), "stim")
    # The east side is blocked by the tall bar, so the word goes west, 4mm off.
    assert label.x1 == pytest.approx(rule_x - 4.0, abs=1e-6)


def test_label_offset_defaults_to_the_theme_gap():
    default, rule_x = _rule_and_label(_bars_and_vline(), "stim")
    near, _ = _rule_and_label(_bars_and_vline(label_offset=1.0), "stim")
    assert default.x0 - rule_x == pytest.approx(near.x0 - rule_x, abs=1e-6)
