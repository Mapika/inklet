"""Glyph reuse: `text="outline"` as `<defs>` plus `<use>`.

Outlining used to write every occurrence of every letter out in full, which is
why an outlined page came out five to seven times the size of the named-font
one. The same forty letters recur thousands of times in a figure, so each
distinct (face, glyph, size) is defined once and every occurrence after the
first is a `<use>`.

The class of bug that buys: a file that is smaller and draws something else.
So most of these assertions are about the *drawing* -- that the reused page
places the same ink, in the same order, at the same coordinates -- and only
one is about the byte count.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

import inklet
from inklet.core import Diagram
from inklet.render.glyphs import placed_glyphs, to_path
from inklet.render.svg import to_svg
from inklet.typeset import shape
from inklet.typeset.outline import text_to_paths

SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"


def block(text: str = "banana bandana", **kwargs) -> Diagram:
    return Diagram(prim=shape(text, font="DejaVu Sans", size=4.0, **kwargs))


def parts(document: str) -> tuple[list, list]:
    """(the glyph definitions, the uses of them)."""
    root = ET.fromstring(document)
    defs = root.find(f"{SVG}defs")
    return (list(defs.iter(f"{SVG}path")) if defs is not None else [],
            list(root.iter(f"{SVG}use")))


# -- the reuse itself ------------------------------------------------------


def test_a_repeated_letter_is_defined_once_and_used_every_time():
    glyphs, uses = parts(to_svg(block("aaaa"), text="outline"))
    assert len(glyphs) == 1
    assert len(uses) == 4
    assert {u.get(f"{XLINK}href") for u in uses} == {"#" + glyphs[0].get("id")}


def test_distinct_letters_get_distinct_definitions():
    glyphs, uses = parts(to_svg(block("abcabc"), text="outline"))
    assert len(glyphs) == 3
    assert len(uses) == 6


def test_the_same_letter_at_two_sizes_is_two_definitions():
    """The size is baked into the definition rather than carried as a
    `scale()` on each use: a figure sets its type in two or three sizes and
    holds thousands of glyphs, so a second alphabet is cheaper than a
    transform on every letter of the page."""
    small = Diagram(prim=shape("aaa", font="DejaVu Sans", size=2.0))
    large = Diagram(prim=shape("aaa", font="DejaVu Sans", size=4.0))
    glyphs, uses = parts(to_svg(Diagram(children=(small, large)), text="outline"))
    assert len(glyphs) == 2
    assert len(uses) == 6


def test_a_use_is_placed_by_x_and_y_alone():
    """No transform, because the definition is already in millimetres at the
    size it is used -- which is what makes a use forty bytes instead of a
    hundred and forty."""
    _glyphs, uses = parts(to_svg(block("ab"), text="outline"))
    for use in uses:
        assert use.get("transform") is None
        assert use.get("x") is not None and use.get("y") is not None


def test_a_space_defines_nothing_and_uses_nothing():
    """An inkless glyph would otherwise go out as `<path d=""/>` and be
    referenced once per word boundary."""
    solid, _ = parts(to_svg(block("aa"), text="outline"))
    spaced, uses = parts(to_svg(block("a a"), text="outline"))
    assert len(spaced) == len(solid) == 1
    assert len(uses) == 2


def test_the_definitions_precede_what_refers_to_them():
    document = to_svg(block(), text="outline")
    assert document.index("<defs>") < document.index("<use")


# -- what it must still draw ----------------------------------------------


def sole_path(prim):
    """The one path an uncoloured block outlines to. `text_to_paths` groups by
    fill, and a block with no `{fill|text}` markup has exactly one group."""
    (path, fill), = text_to_paths(prim)
    assert fill is None
    return path



def test_the_reused_page_places_the_ink_the_inline_outline_placed():
    """`to_path(placed_glyphs(...))` is the geometry the defs and uses are
    spelled from, so this is the reuse machinery checked against the tree
    transform that `inklet.outline_text` has always used."""
    for text in ("banana bandana", "Cu O and H", "one"):
        prim = shape(text, font="DejaVu Sans", size=4.0, width=40.0)
        assert to_path(placed_glyphs(prim)) == sole_path(prim)


def test_justification_slack_is_paid_at_each_space():
    """A run now ends wherever inline markup changes, so banking the slack to
    the end of a run opens one five-space hole in front of every bold word."""
    prim = shape("a justified line of prose that has to wrap somewhere here",
                 font="DejaVu Sans", size=3.0, width=45.0, align="justify")
    assert any(line.word_spacing for line in prim.lines)
    assert to_path(placed_glyphs(prim)) == sole_path(prim)


def test_the_outlined_page_has_no_text_left_in_it():
    document = to_svg(block(), text="outline")
    assert f"{SVG}text" not in document
    assert "font-family" not in document


def test_outlining_is_deterministic():
    page = block()
    assert to_svg(page, text="outline") == to_svg(page, text="outline")


def test_reuse_is_smaller_than_writing_every_letter_out():
    """The number the whole exercise is for: the corpus measures 40-58%
    smaller than the same page with every occurrence spelled out."""
    page = block("The quick brown fox jumps over the lazy dog. " * 12,
                 width=80.0)
    spelled_out = len(to_svg(inklet.outline_text(page)))
    reused = len(to_svg(page, text="outline"))
    assert reused < 0.7 * spelled_out


# -- ids -------------------------------------------------------------------


def test_glyph_ids_step_out_of_the_way_of_node_ids():
    """`G0` is a legal node id, and two elements with one id is a broken
    document. The tree is walked before a single glyph is registered."""
    page = Diagram(children=(block("aa"),), id="G0")
    document = to_svg(page, text="outline")
    glyphs, uses = parts(document)
    assert [g.get("id") for g in glyphs] == ["inklet-G0"]
    assert uses[0].get(f"{XLINK}href") == "#inklet-G0"
    assert document.count('id="G0"') == 1


# -- per-run colour --------------------------------------------------------


def test_a_recoloured_run_paints_only_its_own_glyphs():
    page = Diagram(prim=shape("plain {#cc0000|red} plain",
                              font="DejaVu Sans", size=4.0))
    document = to_svg(page, text="outline")
    _glyphs, uses = parts(document)
    reds = [u for u in uses if u.get("fill") == "#cc0000"]
    assert 0 < len(reds) < len(uses)
    assert all(u.get("fill") is None for u in uses if u not in reds)


def test_a_recoloured_run_is_a_tspan_fill_when_text_stays_text():
    page = Diagram(prim=shape("plain {#cc0000|red} plain",
                              font="DejaVu Sans", size=4.0))
    root = ET.fromstring(to_svg(page))
    spans = list(root.iter(f"{SVG}tspan"))
    assert [s.get("fill") for s in spans].count("#cc0000") == 1


def test_a_line_with_no_runs_is_untouched_by_any_of_this():
    """The fast path is most of every figure: one `<text>`, no spans."""
    root = ET.fromstring(to_svg(block("plain label")))
    assert list(root.iter(f"{SVG}tspan")) == []


# -- refusals --------------------------------------------------------------


def test_a_text_prim_with_no_face_cannot_be_outlined():
    from inklet.core.prims import TextLine, TextPrim
    prim = TextPrim(lines=(TextLine("x", 2.0, 0.0, 0.0),), font_family="Inter",
                    font_size=2.8, ascent=2.0, descent=0.6)
    with pytest.raises(ValueError, match="font_path"):
        placed_glyphs(prim)


def test_an_unknown_text_mode_is_refused():
    with pytest.raises(ValueError):
        to_svg(block(), text="outlines")
