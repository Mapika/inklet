"""Pins the text, label and date behaviour that the docs now describe.

Most of this group is documentation. These tests fix the measurable facts the
new prose states: where `align` puts the lines of a block, where `anchor` and
`offset` put a label, that a band y scale names its rows, that the italic
markup in the guide really sets an italic run, and that a date ends make a
calendar axis.
"""
import re
from pathlib import Path

import pytest

import inklet as i
from inklet.core import TextPrim
from inklet.plot import notes
from inklet.plot.panel import Panel

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "src" / "inklet" / "guide.md"


def _offsets(prim):
    return [prim.line_offset(line) for line in prim.lines]


def test_align_start_puts_every_line_on_the_left_edge():
    start = i.text("Excess\n14.8 M", align="start").prim
    centred = i.text("Excess\n14.8 M").prim

    assert start.align == "start"
    assert _offsets(start) == [0.0, 0.0]
    # The default centres the shorter second line, so its start moves right.
    assert centred.align == "center"
    assert _offsets(centred)[1] > 0.1


def test_align_right_and_left_spellings_are_the_same_as_end_and_start():
    assert i.text("a\nb", align="right").prim.align == "end"
    assert i.text("a\nb", align="left").prim.align == "start"


def test_annotate_and_title_pass_align_to_their_text():
    # The callout forwards `align` to its label, and `inklet.title` to `text`.
    p = i.panel(70, 40, x=(0, 1), y=(0, 1))
    p.annotate(0.1, 0.9, "peak\nvalue", side="ne", align="start")
    aligns = [node.prim.align for node in p.build().walk() if isinstance(node.prim, TextPrim)]
    assert aligns == ["start"]
    assert i.title("a\nb", align="start").prim.align == "start"


def test_text_anchor_nw_puts_the_top_left_corner_on_the_datum():
    p = i.panel(60, 30, x=(0, 1), y=(0, 1))
    datum = p.point(0.5, 0.5)
    box = notes.text_at(p, 0.5, 0.5, "Hello", anchor="nw", offset=(1, 2)).bbox

    assert box.x0 == pytest.approx(datum.x + 1)
    assert box.y0 == pytest.approx(datum.y + 2)


def test_text_offset_dy_moves_the_label_down_the_page():
    p = i.panel(60, 30, x=(0, 1), y=(0, 1))
    level = notes.text_at(p, 0.5, 0.5, "Hello", anchor="w").bbox
    lower = notes.text_at(p, 0.5, 0.5, "Hello", anchor="w", offset=(0, 1)).bbox
    right = notes.text_at(p, 0.5, 0.5, "Hello", anchor="w", offset=(1, 0)).bbox

    assert lower.y0 - level.y0 == pytest.approx(1.0)
    assert right.x0 - level.x0 == pytest.approx(1.0)


def test_panel_text_documents_every_anchor_and_the_offset_direction():
    doc = " ".join(Panel.text.__doc__.split())
    for anchor in ("c", "n", "ne", "e", "se", "s", "sw", "w", "nw"):
        assert f'"{anchor}"' in doc, anchor
    assert "`dy` moves it **down**" in doc


def test_text_docstring_documents_align_values():
    doc = i.text.__doc__
    for value in ("center", "start", "end", "justify"):
        assert f'"{value}"' in doc, value


def test_band_y_scale_names_rows_top_down_and_draws_their_labels():
    countries = ["Chile", "Peru", "Brazil", "Mexico"]
    ratio = [1.2, 0.8, 2.1, 1.6]
    low = [0.9, 0.5, 1.7, 1.1]
    high = [1.5, 1.2, 2.6, 2.0]

    p = i.panel(60, 40, x=(0, 3), y=i.band(countries[::-1]))
    rows = list(zip(ratio, countries))
    p.errorbars(rows, xerr=[(r - lo, hi - r) for r, lo, hi in zip(ratio, low, high)], cap=0)
    p.scatter(rows, name="Ratio", size=2.2)
    p.axes(x="Ratio (95% CI)")

    # The list is read bottom-up, so reversing it puts Chile at the top.
    assert p.point(1, "Chile").y < p.point(1, "Mexico").y
    doc = i.document()
    doc.add("a", p)
    svg = doc.compile().to_svg()
    for name in countries:
        assert f">{name}<" in svg, name


def test_guide_has_the_italic_symbol_example_and_it_sets_italic_runs():
    guide = GUIDE.read_text(encoding="utf-8")
    assert '"//m//_{ν}^{2} (eV^{2})"' in guide
    assert '"//E//_{0} (eV)"' in guide

    prim = i.text("//m//_{ν}^{2} (eV^{2})", size=i.pt(11)).prim
    italic = [run.text for line in prim.lines for run in line.runs
              if "Italic" in str(run.font_path)]
    upright = [run.text for line in prim.lines for run in line.runs
               if "Italic" not in str(run.font_path)]
    assert italic == ["m"]
    assert "(eV" in "".join(upright)


def test_guide_points_dates_at_the_calendar_axis_not_decimal_years():
    guide = GUIDE.read_text(encoding="utf-8")
    assert re.search(r"x=\('2023-01-01', '2024-06-30'\)", guide)
    assert "decimal years" in guide


def test_date_ends_and_date_points_make_a_calendar_axis():
    import datetime as dt

    months = [dt.date(2023, m, 1) for m in range(1, 13)]
    p = i.plot_spec(60, 30, x=("2023-01-01", "2023-12-31"), y=(0, 10))
    p.line(list(zip(months, range(12))), name="cases")
    p.axes(x="Month", y="Cases")
    doc = i.document()
    doc.add("a", p)
    svg = doc.compile().to_svg()
    assert "Jan 2023" in svg
    assert "Apr" in svg
