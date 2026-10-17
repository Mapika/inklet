"""Regression tests for the `crashes` group: jwst_wasp39b_2023 #1 and #2,
atlas_higgs_2022 #1 and #5, and yengo_height_2022 #1.

Each test reproduces one logged issue. Geometry is checked as numbers (bounds,
colours in the SVG, lint codes), never as pixels.
"""

from __future__ import annotations

import warnings

import pytest

import inklet as i
from inklet.core import DiagramError, resolve
from inklet.draw.coords import plot_area


def _compile(panel, width=100):
    doc = i.document(width=width)
    doc.add("a", panel)
    return doc.compile()


def _placed_labels(panel):
    """The absolute boxes of every callout label, and the plot area, in one frame."""
    node = panel.build()
    placed = resolve(node)
    labels = [placed[n.id].bbox for n in node.walk() if n.kind == "annotation-label"]
    return labels, plot_area(node)


# -- jwst_wasp39b_2023 #1: annotate(color=) -----------------------------------


def test_annotate_color_paints_the_words_and_the_leader():
    q = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
    q.line([(0, 0.2), (1, 0.8)], stroke="#000000", name="line")
    q.annotate(0.2, 0.3, "callout", side="ne", color="#a94400")
    svg = _compile(q).to_svg()
    # The words are set in the colour, as text(color=) sets them.
    assert 'fill="#a94400"' in svg and ">callout</text>" in svg
    # And the leader is drawn in it, so the callout reads as one annotation.
    assert [line for line in svg.splitlines()
            if "<path" in line and 'stroke="#a94400"' in line]


def test_annotate_text_fill_still_wins_over_color():
    q = i.plot_spec(80, 40, x=(0, 1), y=(0, 1))
    q.annotate(0.2, 0.3, "callout", side="ne", color="#a94400", text_fill="#0000ff")
    svg = _compile(q).to_svg()
    assert 'fill="#0000ff"' in svg and ">callout</text>" in svg


# -- atlas_higgs_2022 #1: errorbars(stroke=<list>) -----------------------------


def test_errorbars_takes_one_stroke_per_point_and_renders():
    p = i.plot_spec(60, 40, x=(0, 1), y=(0, 1))
    p.errorbars([(0.3, 0.5), (0.7, 0.5)], yerr=[(0.1, 0.1), (0.1, 0.1)],
                stroke=["#ff0000", "#0000ff"])
    svg = _compile(p, width=80).to_svg()
    # One bar and two caps per point, each in its own colour.
    assert svg.count("#ff0000") == 3 and svg.count("#0000ff") == 3


def test_errorbars_stroke_list_must_match_the_points_at_the_call():
    # A panel draws eagerly, so the mismatch is refused where it is written.
    p = i.panel(60, 40, x=(0, 1), y=(0, 1))
    with pytest.raises(DiagramError, match=r"stroke= has 3 values for 2 points"):
        p.errorbars([(0.3, 0.5), (0.7, 0.5)], yerr=0.1,
                    stroke=["#ff0000", "#0000ff", "#00ff00"])


def test_errorbars_single_stroke_still_paints_every_whisker():
    p = i.plot_spec(60, 40, x=(0, 1), y=(0, 1))
    p.errorbars([(0.3, 0.5), (0.7, 0.5)], yerr=0.1, stroke="#123456")
    assert "#123456" in _compile(p, width=80).to_svg()


# -- yengo_height_2022 #1 and jwst_wasp39b_2023 #2: thinning explicit ticks ---

LENGTH_MB = [249.25, 243.20, 198.02, 191.15, 180.92, 171.12, 159.14, 146.36,
             141.21, 135.53, 135.01, 133.85, 115.17, 107.35, 102.53, 90.35,
             81.20, 78.08, 59.13, 63.03, 48.13, 51.30]


def _chromosome_panel():
    offsets, total = [], 0.0
    for length in LENGTH_MB:
        offsets.append(total + length / 2)
        total += length
    names = {round(c, 6): str(n + 1) for n, c in enumerate(offsets)}
    p = i.plot_spec(170, 40, x=(0, total), y=(0, 30))
    p.scatter([(1, 1)], size=1)
    p.axes(x="Chromosome", x_options=dict(ticks=offsets, rotate=90,
                                          format=lambda v: names[round(v, 6)]))
    return p


def test_thinning_explicit_labelled_ticks_compiles():
    fig = _compile(_chromosome_panel(), width=180)
    report = fig.report()
    assert "TICKS_DROPPED" in report and "explicitly supplied ticks" in report


def test_thinned_ticks_name_their_labels_in_the_lint_message():
    fig = _compile(_chromosome_panel(), width=180)
    (line,) = [line for line in fig.report().splitlines() if "TICKS_DROPPED" in line]
    # The labels come from the rotated text, so they read as the chromosome
    # numbers the caller wrote, not as an empty list.
    assert "and" in line and "more" in line


def test_thinned_explicit_ticks_are_not_a_python_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        p = i.panel(20, 20, x=(0, 14), y=(0, 1))
        p.axis("bottom", ticks=list(range(15)))
    assert not [w for w in caught if "explicitly supplied" in str(w.message)]


def test_thinning_is_reported_once_by_lint_and_not_as_a_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig = _compile(_chromosome_panel(), width=180)
        report = fig.report()
    assert not [w for w in caught if "explicitly supplied" in str(w.message)]
    assert report.count("TICKS_DROPPED") == 1


def test_thin_false_keeps_every_explicit_tick():
    p = i.panel(20, 20, x=(0, 14), y=(0, 1))
    p.axis("bottom", ticks=list(range(15)), thin=False)
    assert "TICKS_DROPPED" not in _compile(p, width=60).report()


# -- atlas_higgs_2022 #5: a callout stays on its panel ------------------------


@pytest.mark.parametrize("side", ["n", "ne", "e", "se", "s", "sw", "w", "nw"])
@pytest.mark.parametrize("leader", [False, True])
def test_callout_whose_point_lies_below_the_range_stays_inside(side, leader):
    # The point is about 4 mm under the bottom of a log axis, so no side is
    # clear of the edge. The label is held on the panel instead of sliding off.
    p = i.panel(60, 40, x=(0.05, 300), y=i.log((1e-3, 1)), clip=True)
    p.scatter([(0.5, 0.05), (2, 0.01), (50, 0.2)], size=1.2, name="pts")
    p.axes(x="x", y="y")
    p.annotate(10, 5e-4, "c", side=side, leader=leader)
    (box,), area = _placed_labels(p)
    assert area.x0 - 1e-6 <= box.x0 and box.x1 <= area.x1 + 1e-6
    assert area.y0 - 1e-6 <= box.y0 and box.y1 <= area.y1 + 1e-6


def test_callout_inside_false_is_allowed_to_leave_the_plot_area():
    p = i.panel(60, 40, x=(0.05, 300), y=i.log((1e-3, 1)), clip=True)
    p.scatter([(0.5, 0.05)], size=1)
    p.axes(x="x", y="y")
    p.annotate(10, 5e-4, "c", side="n", inside=False, leader=False)
    (box,), area = _placed_labels(p)
    assert box.y0 > area.y1 - 1e-6


def test_callout_keeps_a_clear_side_where_it_asked():
    p = i.panel(60, 40, x=(0, 10), y=(0, 10), clip=True)
    p.scatter([(5, 5)], size=1)
    p.axes(x="x", y="y")
    p.annotate(5, 5, "c", side="ne", leader=False)
    (box,), area = _placed_labels(p)
    datum = p.point(5, 5)
    assert box.center.x > datum.x and box.center.y < datum.y    # up and to the right
    assert area.x0 <= box.x0 and box.x1 <= area.x1
    assert area.y0 <= box.y0 and box.y1 <= area.y1
