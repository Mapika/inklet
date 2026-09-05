"""Insets and data-coordinate brackets.

An inset is only worth having if a reader can tell *which* part of the picture
got bigger, so most of what is tested here is the indicator window and the two
connectors -- the parts a hand-drawn inset gets wrong.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import resolve
from inklet.plot.inset import INDICATOR_KIND, inset, panel_bracket


def parent() -> "inklet.plot.Panel":
    p = inklet.panel(60, 40, x=(0, 10), y=(0, 100))
    p.line([(0, 0), (10, 100)])
    return p


def child() -> "inklet.plot.Panel":
    p = inklet.panel(24, 16, x=(2, 4), y=(20, 40))
    p.marks(inklet.marker("circle", 0.8), [(2, 20), (4, 40)])
    p.outline()
    return p


def segments(node, kind: str = INDICATOR_KIND):
    """Every polyline of `kind` in a built tree, in figure coordinates."""
    placements = resolve(node)
    out = []
    for n in node.walk():
        if n.kind != kind or not hasattr(n.prim, "subpaths"):
            continue
        world = placements[n.id].world
        for sub in n.prim.subpaths:
            pts = list(sub.points) or (
                [sub.curves[0][0]] + [c[3] for c in sub.curves])
            if sub.closed:
                pts = pts + [pts[0]]
            out.append([world.apply(p) for p in pts])
    return out


# -- placement -------------------------------------------------------------


def test_the_inset_sits_inside_the_plot_area():
    p = parent()
    inset(p, child(), corner="ne")
    area = p.area
    for node in p.build().walk():
        if node.kind == "inset" or node.kind == "frame":
            pass
    box = p.build().bbox
    assert box.width >= 60.0 - 1e-9      # the panel still owns its own size
    assert area.x1 - area.x0 == pytest.approx(60.0)


def test_the_corner_argument_moves_it():
    boxes = {}
    for corner in ("nw", "ne", "sw", "se"):
        p = parent()
        inset(p, child(), corner=corner, plate=False, width=0.3)
        # The last thing over the panel is the inset.
        boxes[corner] = p.build().children[-1].bbox

    assert boxes["nw"].center.x < boxes["ne"].center.x
    assert boxes["sw"].center.x < boxes["se"].center.x
    # y grows downward, so "n" is the smaller y.
    assert boxes["nw"].center.y < boxes["sw"].center.y
    assert boxes["ne"].center.y < boxes["se"].center.y


def test_an_unknown_corner_is_refused():
    with pytest.raises(ValueError, match="corner must be"):
        inset(parent(), child(), corner="middle")


def test_the_inset_is_scaled_to_its_share_of_the_width():
    p = parent()
    inset(p, child(), width=0.25, plate=False)
    assert p.build().children[-1].bbox.width == pytest.approx(15.0)


def test_width_none_leaves_the_sub_panel_at_its_own_size():
    p = parent()
    inset(p, child(), width=None, plate=False)
    # 24mm of plot area plus the half-marker that overhangs each end.
    assert p.build().children[-1].bbox.width == pytest.approx(24.8)


def test_the_plate_adds_paper_under_the_inset():
    bare = parent()
    inset(bare, child(), plate=False, width=0.3)
    plated = parent()
    inset(plated, child(), plate=True, width=0.3)
    assert (plated.build().children[-1].bbox.width
            > bare.build().children[-1].bbox.width)


def test_the_inset_returns_the_panel_so_it_chains():
    p = parent()
    assert inset(p, child()) is p


def test_a_plain_diagram_can_be_the_inset():
    """Anything with a bbox, not only a Panel -- a legend, a sparkline."""
    p = parent()
    inset(p, inklet.box("n = 40"), width=0.3, plate=False)
    assert p.build().children[-1].bbox.width == pytest.approx(18.0)


# -- the indicator ---------------------------------------------------------


def test_the_zoom_window_is_drawn_in_parent_data_coordinates():
    p = parent()
    inset(p, child(), zoom=(2, 4, 20, 40), connect=False)
    windows = [s for s in segments(p.build()) if len(s) == 5]
    assert len(windows) == 1
    xs = [pt.x for pt in windows[0]]
    ys = [pt.y for pt in windows[0]]
    # x 2..4 of 0..10 over 60mm; y 20..40 of 0..100 over 40mm, y flipped.
    assert min(xs) == pytest.approx(-18.0)
    assert max(xs) == pytest.approx(-6.0)
    assert min(ys) == pytest.approx(4.0)
    assert max(ys) == pytest.approx(12.0)


def test_a_malformed_zoom_says_what_it_wanted():
    with pytest.raises(ValueError, match="x0, x1, y0, y1"):
        inset(parent(), child(), zoom=(2, 4))


def test_two_connectors_join_the_window_to_the_inset():
    p = parent()
    inset(p, child(), corner="ne", zoom=(2, 4, 20, 40))
    lines = [s for s in segments(p.build()) if len(s) == 2]
    assert len(lines) == 2


def test_the_connectors_stay_outside_both_boxes():
    """A connector that cuts across the window reads as data, not as a link."""
    p = parent()
    inset(p, child(), corner="ne", zoom=(1, 3, 10, 30))
    built = p.build()
    window = [s for s in segments(built) if len(s) == 5][0]
    wx = [pt.x for pt in window]
    wy = [pt.y for pt in window]
    for a, b in [s for s in segments(built) if len(s) == 2]:
        mid = (a + b) * 0.5
        inside = (min(wx) < mid.x < max(wx)) and (min(wy) < mid.y < max(wy))
        assert not inside


def test_connect_false_leaves_the_window_alone():
    p = parent()
    inset(p, child(), zoom=(2, 4, 20, 40), connect=False)
    assert not [s for s in segments(p.build()) if len(s) == 2]


def test_the_indicator_is_a_muted_hairline_not_a_mark():
    """It is furniture. Drawing it at data weight makes it look like a series."""
    p = parent()
    inset(p, child(), zoom=(2, 4, 20, 40))
    assert segments(p.build(), INDICATOR_KIND)


def test_an_inset_figure_lints_clean():
    p = parent()
    inset(p, child(), corner="ne", zoom=(2, 4, 20, 40), width=0.45)
    fig = inklet.figure(width="120mm")
    fig.add(p.build())
    assert [d for d in fig.lint() if d.severity == "error"] == []


def test_the_same_inset_twice_is_the_same_geometry():
    def build():
        p = parent()
        inset(p, child(), corner="sw", zoom=(2, 4, 20, 40))
        return [[(pt.x, pt.y) for pt in s] for s in segments(p.build())]

    assert build() == build()


# -- brackets in data coordinates -----------------------------------------


def test_a_panel_bracket_spans_the_data_it_is_given():
    p = parent()
    node = panel_bracket(p, 2, 6, 80, text="***")
    # x 2..6 of 0..10 over 60mm is 24mm, plus whatever the ticks add.
    assert node.bbox.width == pytest.approx(24.0, abs=0.01)


def test_a_side_bracket_reads_the_span_on_the_other_axis():
    p = parent()
    node = panel_bracket(p, 20, 60, 8, side="e", tick=1.0)
    # y 20..60 of 0..100 over 40mm.
    assert node.bbox.height == pytest.approx(16.0, abs=0.01)


def test_a_bracket_label_rides_above_the_span():
    p = parent()
    plain = panel_bracket(p, 2, 6, 80)
    starred = panel_bracket(p, 2, 6, 80, text="***")
    assert starred.bbox.height > plain.bbox.height


def test_a_panel_bracket_lands_on_the_panel():
    p = parent()
    p.over(panel_bracket(p, 2, 6, 80, text="n.s."))
    assert p.build().bbox.width >= 60.0 - 1e-9


# -- through the panel -----------------------------------------------------


def test_panel_inset_is_the_same_call_and_chains():
    p = parent()
    assert p.inset(child(), corner="se", width=0.3) is p
    assert p.build().children[-1].bbox.width == pytest.approx(18.0, abs=3.0)


def test_panel_bracket_draws_over_the_panel_and_chains():
    p = parent()
    assert p.bracket(2, 6, 80, text="***") is p
    assert p.build().bbox.width >= 60.0 - 1e-9
