"""`BREAK_DISTORTS` -- the rule that lets `inklet.broken` exist.

A broken axis is the only furniture in the library that makes the picture
disagree with the numbers deliberately, so the tests here are about the two
things the rule owes the reader: it speaks when a comparison has been rescaled,
and it is silent otherwise -- structurally silent, on every figure that has no
break at all, which is what the corpus check turns on.

The scale and the glyph are tested in `tests/test_plot_broken_axis.py`.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import resolve
from inklet.diagnostics.break_rules import BREAK_RATIO_TOLERANCE
from inklet.diagnostics.rules import RULES
from inklet.draw.annotate import BRACKET_KIND
from inklet.draw.coords import as_drawn
from inklet.plot import broken

#: One plate that ran away with it, three that did not: the case an author
#: reaches for a break to draw, and the case where reaching for one costs the
#: reader the comparison.
NAMES = ["wt", "dA", "dB", "dC"]
COUNTS = [12.0, 31.0, 44.0, 385.0]
BREAK = (45.0, 330.0)


def counts_panel(y, values=COUNTS, *, marked: bool = False):
    p = inklet.panel(60.0, 40.0, x=NAMES, y=y)
    p.bars(NAMES, values)
    if marked:
        p.break_marks()
    p.axes(x="strain", y="colonies")
    return p


def findings(node, code: str = "BREAK_DISTORTS"):
    fig = inklet.figure(width="90mm")
    fig.add(node)
    return [d for d in fig.lint() if d.code == code]


def messages(node, code: str = "BREAK_DISTORTS") -> list[str]:
    return [d.message for d in findings(node, code)]


# --- the rule is registered --------------------------------------------------


def test_the_rule_is_in_the_table_under_its_own_name() -> None:
    assert "BREAK_DISTORTS" in RULES


def test_it_is_graded_info_because_a_break_is_a_decision_not_a_fault() -> None:
    """What the finding asks for is a caption, not a redraw. Grading it a
    warning would make a legitimate choice look like a bug."""
    found = findings(counts_panel(broken((0.0, 400.0), breaks=[BREAK])).build())
    assert found and all(d.severity == "info" for d in found)


# --- silence ------------------------------------------------------------------


def test_an_unbroken_axis_is_never_reported() -> None:
    assert messages(counts_panel((0.0, 400.0)).build()) == []


def test_a_figure_with_no_panel_at_all_is_never_reported() -> None:
    """The rule reads a note only `plot.scale.broken` causes to be written, so
    the whole existing corpus is out of its reach by construction."""
    fig = inklet.figure(width="60mm")
    fig.add(inklet.box("hello", width=20.0, height=10.0))
    assert [d for d in fig.lint() if d.code == "BREAK_DISTORTS"] == []


def test_bars_that_all_live_in_one_band_are_not_reported() -> None:
    """Inside a band the millimetres per unit are the ordinary ones and every
    comparison the reader makes is the true one. The break is above them and
    says nothing about them."""
    inside = [12.0, 31.0, 40.0, 44.0]
    assert messages(counts_panel(broken((0.0, 400.0), breaks=[BREAK]),
                                 inside).build()) == []


def test_a_lone_bar_across_a_band_boundary_still_reports_the_crossing() -> None:
    """One mark is not enough for a ratio, but a bar drawn straight through a
    gap has a length that stands for nothing whatever it is compared with."""
    p = inklet.panel(60.0, 40.0, x=["only"], y=broken((0.0, 400.0), breaks=[BREAK]))
    p.bars(["only"], [385.0])
    p.axes(y="colonies")
    found = messages(p.build())
    assert len(found) == 1
    assert "cross" in found[0]


# --- the crossing heuristic ---------------------------------------------------


def test_a_bar_drawn_through_the_break_is_reported() -> None:
    found = messages(counts_panel(broken((0.0, 400.0), breaks=[BREAK])).build())
    assert any("filled mark" in m and "cross" in m for m in found), found


def test_the_crossing_is_reported_whether_or_not_the_glyph_is_drawn() -> None:
    """Marking a bar does not make its length mean something again, so the
    finding cannot be silenced by drawing the journal's slashes on it."""
    scale = broken((0.0, 400.0), breaks=[BREAK])
    def crossings(marked: bool) -> list[str]:
        # Less the panel's generated name, which differs between two builds.
        return [m.split("in ")[0]
                for m in messages(counts_panel(scale, marked=marked).build())
                if "cross" in m]
    assert crossings(False) == crossings(True) != []


def test_the_crossing_finding_points_at_the_bar_it_means() -> None:
    scale = broken((0.0, 400.0), breaks=[BREAK])
    crossing = [d for d in findings(counts_panel(scale).build())
                if "cross" in d.message]
    assert len(crossing) == 1
    assert len(crossing[0].targets) == 1
    assert crossing[0].where.height > 10.0     # the tall bar, not a tick


def test_the_hint_names_the_glyph_and_still_asks_for_a_caption() -> None:
    scale = broken((0.0, 400.0), breaks=[BREAK])
    hint = [d.hint for d in findings(counts_panel(scale).build())
            if "cross" in d.message][0]
    assert "break_marks" in hint and "caption" in hint


# --- the proportion heuristic -------------------------------------------------


def test_two_bars_the_page_shows_out_of_proportion_are_reported() -> None:
    """385 against 31 is thirty-fold in the data. On a broken axis it is under
    four-fold on the page, and nothing in the drawing says so."""
    scale = broken((0.0, 400.0), breaks=[BREAK])
    found = [m for m in messages(counts_panel(scale).build()) if "apart" in m]
    assert len(found) == 1
    assert "385" in found[0], found[0]
    page = float(found[0].split(" apart")[0].split()[-1].rstrip("x"))
    data = float(found[0].split("says ")[1].rstrip("x"))
    assert page < 4.0 < data


def test_the_sentence_leads_with_the_bigger_number() -> None:
    """A reader checking the finding looks for the tall bar first; opening
    with the short one reads as being about the wrong bar."""
    scale = broken((0.0, 400.0), breaks=[BREAK])
    message = [m for m in messages(counts_panel(scale).build()) if "apart" in m][0]
    page = float(message.split(" apart")[0].split()[-1].rstrip("x"))
    data = float(message.split("says ")[1].rstrip("x"))
    assert 1.0 < page < data


def test_the_measured_distortion_is_the_ratio_of_the_two_ratios() -> None:
    scale = broken((0.0, 400.0), breaks=[BREAK])
    found = [d for d in findings(counts_panel(scale).build())
             if "apart" in d.message][0]
    page = float(found.message.split(" apart")[0].split()[-1].rstrip("x"))
    data = float(found.message.split("says ")[1].rstrip("x"))
    stated = float(found.hint.split("x distortion")[0].split()[-1])
    assert stated == pytest.approx(data / page, rel=0.02)
    assert stated > BREAK_RATIO_TOLERANCE


def test_a_break_too_small_to_matter_is_below_the_tolerance() -> None:
    """A gap of ten units out of four hundred moves the ratio by a couple of
    percent, which is the width of the ink and not worth a line in a report."""
    scale = broken((0.0, 400.0), breaks=[(300.0, 310.0)])
    assert [m for m in messages(counts_panel(scale).build()) if "apart" in m] == []


# --- the interaction audit ----------------------------------------------------


def test_a_label_written_at_a_value_inside_the_break_is_not_called_off_panel() -> None:
    """It lands on the nearer band edge, which is inside the plot box. It is in
    the wrong place, and no rule can tell that from a label in the right one --
    but `OFF_PANEL` must not claim it left the panel, because it did not."""
    p = counts_panel(broken((0.0, 400.0), breaks=[BREAK]))
    p.text("dB", 200.0, "n.s.", anchor="s")
    assert messages(p.build(), "OFF_PANEL") == []


def test_a_bar_cut_by_the_break_glyph_is_not_called_off_panel() -> None:
    """The glyph erases a strip of a bar the panel legitimately does not draw.
    Nothing there is text, so `OFF_PANEL` is structurally unaffected -- this
    pins that it stays so."""
    p = counts_panel(broken((0.0, 400.0), breaks=[BREAK]), marked=True)
    assert messages(p.build(), "OFF_PANEL") == []


def test_errorbars_across_a_break_draw_and_are_not_reported_as_marks() -> None:
    """A whisker is a stroke, not a filled mark: there is nothing to cut at a
    quarter of a millimetre, and the rule counts filled marks only. A mean
    whose interval spans a break is an author's problem, not a linter's."""
    p = inklet.panel(60.0, 40.0, x=NAMES, y=broken((0.0, 400.0), breaks=[BREAK]))
    p.errorbars([(n, v) for n, v in zip(NAMES, [12.0, 31.0, 44.0, 40.0])],
                yerr=[4.0, 6.0, 8.0, 340.0])
    p.axes(y="colonies")
    assert messages(p.build()) == []


def test_a_bracket_with_no_height_clears_the_drawing_and_misses_the_gap() -> None:
    """It is placed in millimetres above whatever is drawn between its ends,
    so it cannot land in a break by accident. Both bars here are under it."""
    y = broken((0.0, 400.0), breaks=[BREAK])
    p = inklet.panel(60.0, 40.0, x=NAMES, y=y)
    p.bars(NAMES, [12.0, 31.0, 44.0, 40.0])
    p.bracket("wt", "dB", text="***")
    p.axes(y="colonies")
    lo, hi = sorted(p.y.gap_bands()[0])
    node = p.build()
    # Placed above the tallest thing between its ends, which is a 44-count bar
    # well under the break, so it clears the drawing without meeting the gap.
    drawn = [q.bbox for q in resolve(as_drawn(node)).values()
             if q.diagram.kind == BRACKET_KIND]
    assert drawn, "the bracket should be in the tree"
    assert all(not (lo < box.y1 < hi) for box in drawn)
    assert messages(node) == []


def test_a_broken_scale_declares_no_numeric_domain_for_a_key_to_match() -> None:
    """Its `domain` is the two outer ends, not what it covers. Declaring
    (0, 400) would let a key and a picture that genuinely disagree agree on
    paper, which is the one thing `KEY_MISMATCH` exists to catch, so the note
    is left off and the rule stays quiet rather than being lied to."""
    from inklet.plot.scale import _declare_domain, linear

    plain, cut = inklet.box("key"), inklet.box("key")
    _declare_domain(plain, linear((0.0, 400.0)))
    _declare_domain(cut, broken((0.0, 400.0), breaks=[BREAK]))
    assert plain.notes.get("scale_domain") == (0.0, 400.0)
    assert "scale_domain" not in cut.notes
