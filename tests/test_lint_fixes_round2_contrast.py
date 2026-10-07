"""LOW_CONTRAST: translucent text is composited, decorative text opts out.

ISSUES-medicine-econ 5: a pale grey watermark year was a LOW_CONTRAST warning
while a 10% ink one that renders identically was not checked at all, and
there was no way to say the pale year is meant to recede.
"""

from __future__ import annotations

import warnings

import pytest

import inklet as i
from inklet.diagnostics.color import composite, split_alpha
from inklet.diagnostics.decorative import (DECORATIVE_NOTE, decorative,
                                           is_decorative_kind)


def contrast(figure):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return [d for d in figure.lint() if d.code == "LOW_CONTRAST"]


def _year(**text):
    p = i.plot_spec(x=(0, 1), y=(0, 1))
    p.text(.5, .5, "2007", size=i.pt(40), front=False, **text)
    doc = i.preset("scientific.modern").document()
    doc.add("a", p)
    return doc.compile()


@pytest.mark.parametrize("text", [
    dict(text_fill="#e6e8eb"),
    dict(text_fill="#1a1a1a1a"),
    dict(text_fill="#1a1a1a", opacity=0.1),
    dict(text_fill="rgba(26, 26, 26, 0.1)"),
])
def test_a_pale_watermark_is_judged_the_same_however_it_is_made_pale(text):
    (finding,) = contrast(_year(**text))
    assert finding.severity == "warning"
    assert "1.2" in finding.message                      # ~1.2:1 every way
    assert "decorative" in finding.hint                   # large type: say how to opt out


def test_the_message_says_what_a_translucent_colour_paints_as():
    (finding,) = contrast(_year(text_fill="#1a1a1a", opacity=0.1))
    assert "#1a1a1a at 10% opacity (painted as #e8e8e8)" in finding.message
    assert "raise its opacity" in finding.hint


def test_translucent_text_that_is_still_dark_enough_passes():
    assert contrast(_year(text_fill="#1a1a1a", opacity=0.8)) == []
    assert contrast(_year(text_fill="#000000cc")) == []


def test_fully_transparent_text_paints_nothing_and_is_skipped():
    assert contrast(_year(text_fill="#1a1a1a", opacity=0.0)) == []


@pytest.mark.parametrize("text", [
    dict(text_fill="#e6e8eb"),
    dict(text_fill="#1a1a1a", opacity=0.1),
])
def test_a_decorative_kind_opts_out(text):
    assert contrast(_year(kind=i.diagnostics.decorative(), **text)) == []


def test_the_decorative_note_opts_out_too():
    from inklet.core import Rect
    from inklet.diagnostics import lint
    from inklet.typeset import shape

    def label(**notes):
        node = i.Diagram(prim=shape("faint", size=i.pt(8)), kind="label")
        node = node.styled(text_fill="#eeeeee")
        for key, value in notes.items():
            node.note(key, value)
        return node

    page = Rect(-20, -10, 20, 10)
    loud = lint(label(), page=page, rules=["LOW_CONTRAST"])
    quiet = lint(label(**{DECORATIVE_NOTE: True}), page=page, rules=["LOW_CONTRAST"])
    assert [d.code for d in loud] == ["LOW_CONTRAST"]
    assert "decorative" not in loud[0].hint      # small type: no watermark hint
    assert quiet == []


def test_nested_group_opacities_multiply():
    from inklet.core import Rect
    from inklet.diagnostics import lint
    from inklet.typeset import shape

    text = i.Diagram(prim=shape("ink", size=i.pt(8)), kind="label").styled(
        text_fill="#000000")
    inner = i.Diagram(children=(text,)).styled(opacity=0.5)
    outer = i.Diagram(children=(inner,)).styled(opacity=0.5)
    (finding,) = lint(outer, page=Rect(-20, -10, 20, 10), rules=["LOW_CONTRAST"])
    assert "25% opacity" in finding.message


def test_declarations_compose_and_are_idempotent():
    assert decorative() == "label-decorative"
    assert decorative(decorative("label")) == "label-decorative"
    assert is_decorative_kind(i.abutting(decorative("label")))
    assert not is_decorative_kind("label")


def test_alpha_parsing_and_compositing():
    assert split_alpha("#1a1a1a1a") == ("#1a1a1a", pytest.approx(26 / 255))
    assert split_alpha("#0008") == ("#000000", pytest.approx(0x88 / 255))
    assert split_alpha("rgba(0, 0, 0, 50%)") == ("#000000", 0.5)
    assert split_alpha("#123456") == ("#123456", 1.0)
    assert split_alpha("not a colour") is None
    assert composite("#000000", "#ffffff", 0.5) == "#808080"
    assert composite("#1a1a1a", "#ffffff", 0.1) == "#e8e8e8"


def test_a_group_fading_the_label_and_its_box_together_fades_both():
    # `examples/engine_review.py`: a labelled box inside one 60% group. The
    # box fades with the label, so both move toward the paper: the glyph is
    # not composited over the box at full strength.
    from inklet.diagnostics import lint

    def boxed(ink, group=1.0, own=1.0):
        word = i.text("Input", text_fill=ink)
        if own < 1.0:
            word = word.styled(opacity=own)
        node = i.box(word, width=24, height=18, fill="#d5e9f4")
        return node.styled(opacity=group) if group < 1.0 else node

    faded = boxed("#1a1a1a", group=0.6)
    (finding,) = lint(faded, page=faded.bbox, rules=["LOW_CONTRAST"])
    glyph = composite("#1a1a1a", "#ffffff", 0.6)
    box = composite("#d5e9f4", "#ffffff", 0.6)
    assert f"painted as {glyph}" in finding.message and box in finding.message
    assert "3.98:1" in finding.message

    # Black survives the same fade (5.0:1); fading the word alone does not.
    black = boxed("#000000", group=0.6)
    assert lint(black, page=black.bbox, rules=["LOW_CONTRAST"]) == []
    alone = boxed("#000000", own=0.3)
    (finding,) = lint(alone, page=alone.bbox, rules=["LOW_CONTRAST"])
    assert "at 30% opacity" in finding.message
