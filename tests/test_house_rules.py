"""`lint(house=HouseRules(...))`: a figure set's own rules as lint codes."""
from __future__ import annotations

import pytest

import inklet as i
from inklet.diagnostics import HouseRules, lint

PT = 0.3528
HOUSE = HouseRules(stroke_tiers=(0.6 * PT, 0.75 * PT), marker_outlines=False,
                   muted_text=False, bold="letters", keys="outside")


def _codes(node, house=HOUSE):
    return sorted({d.code for d in lint(node, house=house)} & set(i.diagnostics.HOUSE_CODES))


def _clean_panel(w=50, h=35):
    p = i.panel(w, h, x=(0, 1), y=(0, 1))
    p.axes(x="x", y="y")
    p.line([(0, 0), (1, 1)], stroke_width=0.6 * PT, color="#0072b2", name="data")
    p.line([(0, 0.1), (1, 0.9)], stroke_width=0.75 * PT, color="#263238", name="fit")
    p.scatter([(0.3, 0.3), (0.6, 0.6)], color="#0072b2", stroke="none")
    p.scatter([(0.4, 0.2)], color="#0072b2", hollow=True, stroke_width=0.3)
    p.text(0.2, 0.8, "label", text_fill="#0072b2", markup=False)
    return p.build()


def test_house_rules_are_silent_without_house():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], stroke_width=0.9)
    p.text(0.2, 0.8, "**bold** grey", text_fill="#999999")
    assert _codes(p.build(), house=None) == []


def test_a_clean_panel_passes_every_house_rule():
    assert _codes(_clean_panel()) == []


def test_a_stroke_off_the_tiers_is_reported_with_the_nearest_weight():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.axes(x="x", y="y")
    p.line([(0, 0), (1, 1)], stroke_width=0.45, name="heavy")
    found = [d for d in lint(p.build(), house=HOUSE) if d.code == "STROKE_TIER"]
    assert len(found) == 1
    assert "0.45mm" in found[0].message and "0.265" in found[0].hint


def test_axis_strokes_are_the_librarys_and_not_counted():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.axes(x="x", y="y", stroke_width=0.18)
    assert "STROKE_TIER" not in _codes(p.build())


def test_an_outlined_filled_marker_is_reported_and_a_ring_is_not():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.scatter([(0.5, 0.5)], color="#0072b2", stroke="#263238", stroke_width=0.15)
    assert "MARKER_OUTLINE" in _codes(p.build())
    q = i.panel(50, 35, x=(0, 1), y=(0, 1))
    q.scatter([(0.5, 0.5)], color="#0072b2", hollow=True)
    assert "MARKER_OUTLINE" not in _codes(q.build())


def test_grey_text_is_muted_and_coloured_or_ink_text_is_not():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.text(0.5, 0.5, "faint note", text_fill="#90a4ae", markup=False)
    assert "MUTED_TEXT" in _codes(p.build())
    named = HouseRules(muted_text=False, muted_colors=("#607d8b",))
    q = i.panel(50, 35, x=(0, 1), y=(0, 1))
    q.text(0.5, 0.5, "slate note", text_fill="#607d8b", markup=False)
    assert _codes(q.build(), house=named) == ["MUTED_TEXT"]


def test_bold_text_is_reported_unless_it_is_a_panel_letter():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.text(0.5, 0.5, "**loud**", markup=True)
    assert "BOLD_TEXT" in _codes(p.build())
    m = i.panel_mosaic(["a b"], {"a": _clean_panel, "b": _clean_panel},
                       width=140, height=60, label_size=i.pt(8))
    assert "BOLD_TEXT" not in _codes(m)


def test_a_key_inside_a_panel_is_reported():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.axes(x="x", y="y")
    p.line([(0, 0), (1, 1)], name="a")
    p.line([(0, 1), (1, 0)], name="b")
    p.legend()
    found = [d for d in lint(p.build(), house=HOUSE) if d.code == "KEY_IN_PANEL"]
    assert len(found) == 1


def test_house_codes_can_be_acknowledged():
    p = i.panel(50, 35, x=(0, 1), y=(0, 1))
    p.text(0.5, 0.5, "faint", text_fill="#999999", markup=False)
    assert i.diagnostics.house_rules._muted("#263238", HOUSE) is False   # slate ink
    assert i.diagnostics.house_rules._muted("#37474f", HOUSE) is False   # axis slate
    found = [d for d in lint(p.build(), house=HOUSE, expect={"MUTED_TEXT"}) if d.code == "MUTED_TEXT"]
    assert found and all(d.severity == "acknowledged" for d in found)


def test_house_rules_validate_their_fields():
    with pytest.raises(ValueError):
        HouseRules(bold="sometimes")
    with pytest.raises(ValueError):
        HouseRules(stroke_tiers=(0,))
    with pytest.raises(TypeError):
        lint(_clean_panel(), house={"bold": "letters"})
