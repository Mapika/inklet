"""inklet.plot: cutting data at the plot area, and the marks that sit over it."""

from __future__ import annotations

import pytest

from inklet.core import Rect, resolve
from inklet.draw.coords import as_drawn
from inklet.plot import panel

SPIKY = [(x, 40.0 if x == 5 else 1.0 + x / 10) for x in range(11)]


def extent(node) -> Rect:
    """The box the linter would see, which is the box of what was drawn."""
    return as_drawn(node).bbox


def texts(node) -> list[str]:
    return [placed.diagram.prim.text
            for placed in resolve(as_drawn(node)).values()
            if getattr(placed.diagram.prim, "text", None) is not None]


# --- clipping ----------------------------------------------------------------


def test_unclipped_data_reaches_past_the_plot_area() -> None:
    """The default, and the reason it is the default: the spike is visible."""
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.line(SPIKY)
    assert extent(p.build()).y0 < -15.0 - 1e-6


def test_clipping_the_panel_keeps_the_line_inside_the_area() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10), clip=True)
    p.line(SPIKY)
    assert extent(p.build()).y0 == pytest.approx(-15.0, abs=1e-3)


def test_a_single_call_can_clip_on_an_unclipped_panel() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.line(SPIKY, clip=True)
    assert extent(p.build()).y0 == pytest.approx(-15.0, abs=1e-3)


def test_a_single_call_can_opt_out_of_a_clipped_panel() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10), clip=True)
    p.line(SPIKY, clip=False)
    assert extent(p.build()).y0 < -15.0 - 1e-6


def test_clipping_leaves_data_that_already_fits_alone() -> None:
    """No wrapper, no extra nodes: `clip=True` costs nothing on tidy data."""
    inside = [(x, x) for x in range(11)]
    loose = panel(40, 30, x=(0, 10), y=(0, 10))
    loose.line(inside)
    tight = panel(40, 30, x=(0, 10), y=(0, 10), clip=True)
    tight.line(inside)
    assert len(resolve(as_drawn(tight.build()))) == len(resolve(as_drawn(loose.build())))


def test_words_are_never_clipped() -> None:
    """A half-cut word is unreadable, so text is kept whole or not at all."""
    p = panel(40, 30, x=(0, 10), y=(0, 10), clip=True)
    p.text(9.8, 5, "off the edge")
    assert "off the edge" in texts(p.build())


def test_a_twin_axis_inherits_the_panel_s_clipping() -> None:
    """A twin is the same rectangle, so it is clipped by the same decision."""
    spike = [(x, 400.0 if x == 5 else 10.0) for x in range(11)]
    loose = panel(40, 30, x=(0, 10), y=(0, 10))
    loose.twin_y((0, 100)).line(spike)
    tight = panel(40, 30, x=(0, 10), y=(0, 10), clip=True)
    tight.twin_y((0, 100)).line(spike)
    # Both boxes include the twin's own axis furniture; only the data moves.
    assert extent(loose.build()).y0 < -100.0
    assert extent(tight.build()).y0 > -20.0


# --- reference lines ---------------------------------------------------------


def test_a_reference_line_can_carry_its_name() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.hline(5.0, label="threshold")
    assert "threshold" in texts(p.build())


def test_a_rule_label_stays_inside_the_area() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    p.hline(5.0, label="threshold")
    assert extent(p.build()).x1 == pytest.approx(20.0, abs=0.5)


def test_a_rule_label_is_not_clipped_away() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 10), clip=True)
    p.vline(5.0, label="stim")
    assert "stim" in texts(p.build())


# --- brackets ----------------------------------------------------------------


def test_a_bracket_takes_its_text_where_the_height_would_go() -> None:
    p = panel(40, 30, x=["wt", "ko"], y=(0, 10))
    p.bars(["wt", "ko"], [8.0, 3.0])
    p.bracket("wt", "ko", "***")
    assert "***" in texts(p.build())


def test_a_bracket_clears_what_it_covers() -> None:
    """The height nobody wants to recompute: over the tallest bar, not in it."""
    p = panel(40, 30, x=["wt", "ko"], y=(0, 10))
    p.bars(["wt", "ko"], [8.0, 3.0])
    p.bracket("wt", "ko", "***")
    top_of_bars = 15.0 - 30.0 * 0.8
    assert extent(p.build()).y0 < top_of_bars


def test_a_second_bracket_stacks_above_the_first() -> None:
    p = panel(40, 30, x=["wt", "het", "ko"], y=(0, 10))
    p.bars(["wt", "het", "ko"], [8.0, 5.0, 3.0])
    p.bracket("wt", "het", "*")
    first = extent(p.build()).y0
    p.bracket("wt", "ko", "***")
    assert extent(p.build()).y0 < first - 1.0
