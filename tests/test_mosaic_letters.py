"""Panel letters in `panel_mosaic` share one baseline and one header band."""
from __future__ import annotations

import pytest

import inklet as i
from inklet.core import Vec2, resolve
from inklet.draw.annotate import LETTER_KIND


def _factory(w, h):
    p = i.panel(w, h, x=(0, 1), y=(0, 1))
    p.axes(x="x", y="y")
    return p


def _mosaic(names, **kw):
    return i.panel_mosaic([" ".join(names)], {n: _factory for n in names},
                          width=40 * len(names), height=40,
                          label_size=i.pt(8), label_gap=1, **kw)


def _baselines(mosaic):
    placed = resolve(mosaic)
    out = {}
    for node in mosaic.walk():
        if node.kind == LETTER_KIND:
            world = placed[node.id].world
            out[node.prim.lines[0].text] = world.apply(Vec2(0, node.prim.first_baseline)).y
    return out


def test_x_height_ascender_and_descender_letters_share_a_baseline():
    """Measured by ink, `b` sat 0.5 mm below `a` at 8 pt and `j` 1.1 mm."""
    lines = _baselines(_mosaic(list("abgj")))
    assert set(lines) == set("abgj")
    assert max(lines.values()) - min(lines.values()) < 1e-6


def test_every_panel_in_a_row_starts_at_the_same_height():
    records = _mosaic(list("abgj")).notes["panel_mosaic"]
    tops = {records[n]["content"][1] for n in "abgj"}
    assert max(tops) - min(tops) < 1e-6


def test_an_ascender_letter_keeps_its_former_placement():
    """The band is the ascender line, so `b`, which reached it, does not move."""
    from inklet.layout.mosaic import header_text
    head = header_text("b", i.pt(8), weight="bold")
    ink = i.text("b", size=i.pt(8), weight="bold", markup=False, bounds="ink")
    assert head.bbox.height == pytest.approx(ink.bbox.height, abs=0.05)


def test_mosaic_letters_are_panel_letters_to_lint():
    found = [n for n in _mosaic(list("ab")).walk() if n.kind == LETTER_KIND]
    assert len(found) == 2
    assert all(n.style.font_weight == "bold" for n in found)


def test_titles_sit_on_the_letters_baseline():
    m = i.panel_mosaic(["a b"], {"a": _factory, "b": _factory}, width=120, height=40,
                       label_size=i.pt(8), titles={"a": "Shapes", "b": "dogs"})
    placed = resolve(m)
    lines = {}
    for node in m.walk():
        if node.prim is not None and hasattr(node.prim, "lines") and node.prim.lines:
            text = node.prim.lines[0].text
            if text in ("a", "b", "Shapes", "dogs"):
                lines[text] = placed[node.id].world.apply(Vec2(0, node.prim.first_baseline)).y
    assert max(lines.values()) - min(lines.values()) < 0.05



def test_ink_header_bounds_restore_the_former_placement():
    """`header_bounds='ink'` measures each header by its own ink, as before."""
    lines = _baselines(_mosaic(list("ab"), header_bounds="ink"))
    # An x-height `a` sits higher than an ascender `b` once each ink top is
    # put on the slot top.
    assert lines["b"] - lines["a"] > 0.3
    records = _mosaic(list("ab"), header_bounds="ink").notes["panel_mosaic"]
    assert records["a"]["content"][1] < records["b"]["content"][1]


def test_unknown_header_bounds_are_rejected():
    with pytest.raises(ValueError, match="header_bounds"):
        _mosaic(list("ab"), header_bounds="glyphs")


def test_a_multi_line_title_keeps_clear_of_its_panel():
    m = i.panel_mosaic(["a b"], {"a": _factory, "b": _factory}, width=120, height=60,
                       label_size=i.pt(8), titles={"a": "Two\nlines here"})
    placed = resolve(m)
    records = m.notes["panel_mosaic"]
    for node in m.walk():
        prim = node.prim
        if prim is not None and getattr(prim, "lines", None) and len(prim.lines) == 2:
            from inklet.core import Envelope
            from inklet.typeset.outline import text_to_paths
            ink = Envelope.union_all(p.envelope() for p, _ in text_to_paths(prim)).bbox()
            bottom = placed[node.id].world.apply(Vec2(0, ink.y1)).y
            assert bottom < records["a"]["content"][1]
            break
    else:
        raise AssertionError("no two-line title found")
