"""Reference-line labels: clear of the data, on the side asked for, in front.

`hline(label=)` and `vline(label=)` place the word at the end of the rule, and
the search that places it must see every mark on the panel, including marks
drawn after the rule. A labelled rule is drawn in front of the data.
"""

from __future__ import annotations

import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import resolve
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_LINE_KIND
from inklet.plot import panel


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def placed_nodes(p):
    return list(resolve(as_drawn(p.build())).values())


def label_box(p, text):
    boxes = [placed.bbox for placed in placed_nodes(p)
             if getattr(placed.diagram.prim, "text", None) == text]
    assert len(boxes) == 1, f"expected one {text!r} label, found {len(boxes)}"
    return boxes[0]


def rule_centre(p):
    boxes = [placed.bbox for placed in placed_nodes(p)
             if placed.diagram.kind == MARK_LINE_KIND]
    assert len(boxes) == 1
    box = boxes[0]
    return (box.x0 + box.x1) / 2, (box.y0 + box.y1) / 2


def disjoint(a, b) -> bool:
    return a.x1 <= b.x0 or b.x1 <= a.x0 or a.y1 <= b.y0 or b.y1 <= a.y0


def child_index(built, kind) -> int:
    """Paint position of the first direct child holding a node of `kind`."""
    for n, child in enumerate(built.children):
        if any(node.kind == kind for node in child.walk()):
            return n
    raise AssertionError(f"no child of kind {kind!r}")


def mean_histogram():
    """The repro from the agent test: a rule at the mean of 1000 exam scores."""
    rng = random.Random(2)
    scores = [rng.gauss(64, 12) for _ in range(1000)]
    chart = inklet.hist({"s": scores}, x="s", bins=25)
    chart.vline(sum(scores) / len(scores), label="mean 63.9")
    return chart


# --- the label clears the data -----------------------------------------------


def test_the_mean_label_is_not_flagged_against_the_bars():
    diagnostics = mean_histogram().compile().lint()
    assert not [d for d in diagnostics
                if d.code in ("OVERLAP", "CROWDING") and "mean 63.9" in d.message]


def marks_boxes(p):
    """Boxes of the data rectangles, which `rect` draws with kind 'mark'."""
    return [placed.bbox for placed in placed_nodes(p)
            if placed.diagram.kind == "mark"]


def test_a_mark_drawn_after_the_rule_is_avoided():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.vline(5.0, label="stim")
    # Drawn after the rule, over the whole east side, where the label goes first.
    p.rect(5.5, 0.0, 9.5, 10.0, front=True, fill="#888888")
    box = label_box(p, "stim")
    (cover,) = marks_boxes(p)
    assert disjoint(box, cover)
    # East is blocked at every height, so the label has gone west of the line.
    assert box.x1 <= rule_centre(p)[0]


def test_a_label_steps_along_the_rule_into_the_gap_between_marks():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.vline(5.0, label="stim", label_side="e")
    # East of the rule is blocked at both ends, leaving a band in the middle:
    # the label has to step along the rule to find it, and stay on the east.
    p.rect(5.5, 6.0, 9.5, 10.0, front=True, fill="#888888")
    p.rect(5.5, 0.0, 9.5, 4.0, front=True, fill="#888888")
    box = label_box(p, "stim")
    for cover in marks_boxes(p):
        assert disjoint(box, cover)
    assert box.x0 > rule_centre(p)[0]


def test_a_label_with_no_clear_spot_is_still_drawn():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.vline(5.0, label="stim")
    p.rect(0.0, 0.0, 10.0, 10.0, front=True, fill="#888888")
    # Nothing is clear anywhere; the word is kept, at the labelled end.
    box = label_box(p, "stim")
    assert box.x0 > rule_centre(p)[0]


# --- label_side ---------------------------------------------------------------


@pytest.mark.parametrize("side, inside", [("e", "right"), ("w", "left")])
def test_vline_label_side_puts_the_label_on_that_side(side, inside):
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.vline(5.0, label="stim", label_side=side)
    line_x = rule_centre(p)[0]
    box = label_box(p, "stim")
    if inside == "right":
        assert box.x0 > line_x
    else:
        assert box.x1 < line_x


@pytest.mark.parametrize("side", ["n", "s"])
def test_hline_label_side_puts_the_label_on_that_side(side):
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.hline(5.0, label="thr", label_side=side)
    line_y = rule_centre(p)[1]
    box = label_box(p, "thr")
    if side == "n":
        assert box.y1 < line_y          # above: smaller y on the page
    else:
        assert box.y0 > line_y


def test_label_side_keeps_the_label_on_its_side_when_that_side_is_full():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.vline(5.0, label="stim", label_side="e")
    p.rect(0.0, 0.0, 10.0, 10.0, front=True, fill="#888888")
    assert label_box(p, "stim").x0 > rule_centre(p)[0]


@pytest.mark.parametrize("bad", ["right", "left", "n", "top", "E"])
def test_vline_refuses_a_side_it_does_not_have(bad):
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    with pytest.raises(ValueError, match="'e'.*'w'"):
        p.vline(5.0, label="stim", label_side=bad)


@pytest.mark.parametrize("bad", ["e", "w", "right", "north"])
def test_hline_refuses_a_side_it_does_not_have(bad):
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    with pytest.raises(ValueError, match="'n'.*'s'"):
        p.hline(5.0, label="thr", label_side=bad)


def test_an_invalid_label_side_is_refused_even_without_a_label():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    with pytest.raises(ValueError, match="label_side"):
        p.vline(5.0, label_side="right")


# --- a labelled rule is in front -------------------------------------------


def bars(p):
    """Content-layer data, the way a histogram or bar chart draws it."""
    p.bars([2.0, 6.0], [5.0, 8.0], width=2.0)


def test_a_labelled_vline_is_drawn_over_the_bars():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    bars(p)
    p.vline(5.0, label="stim")
    built = p.build()
    assert child_index(built, MARK_LINE_KIND) > child_index(built, "mark")


def test_a_labelled_hline_is_drawn_over_the_bars():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    bars(p)
    p.hline(5.0, label="thr")
    built = p.build()
    assert child_index(built, MARK_LINE_KIND) > child_index(built, "mark")


def test_an_unlabelled_rule_stays_under_the_bars():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    bars(p)
    p.vline(5.0)
    built = p.build()
    assert child_index(built, MARK_LINE_KIND) < child_index(built, "mark")


def test_front_false_keeps_a_labelled_rule_under_the_bars():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    bars(p)
    p.hline(5.0, label="thr", front=False)
    built = p.build()
    assert child_index(built, MARK_LINE_KIND) < child_index(built, "mark")
