"""The front door of the linter: what `inklet.lint` accepts and what it names.

Two things that have nothing to do with any one rule live here. First, the
argument check -- a figure is not a node, and the error has to say so in the
one line an agent will read. Second, the subject naming: a finding is only
actionable if the thing it points at is the thing the author typed, which
takes a walk up the tree whenever the geometry belongs to a generated child.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import Rect
from inklet.diagnostics import lint

PAGE = Rect(0.0, 0.0, 89.0, 50.0)


# -- lint() is for nodes ---------------------------------------------------


def test_linting_a_figure_says_which_call_to_make():
    figure = inklet.Figure(width=80.0)
    figure.add(inklet.box("read"))

    with pytest.raises(TypeError) as caught:
        lint(figure)

    said = str(caught.value)
    assert "Figure.lint()" in said
    assert "page" in said and "paper" in said


def test_linting_something_that_is_not_a_diagram_at_all():
    with pytest.raises(TypeError, match="not int"):
        lint(42)


def test_the_figure_lints_itself_fine():
    figure = inklet.Figure(width=80.0)
    figure.add(inklet.box("read"))

    assert figure.lint() == []


# -- naming a generated child ----------------------------------------------


def test_a_finding_about_outlined_text_names_the_block():
    # `inklet.outline_text` replaces a two-colour text prim with one
    # `kind="glyphs"` child per colour, so the geometry the rule trips over is
    # a path node with a generated id. The author never typed `glyphs3`; they
    # named the block, and that is what the finding has to say.
    block = inklet.text("{#c00|WARM} and cold", size=6.0).named("legend-note")
    outlined = inklet.outline_text(block)
    off = outlined.translated(200.0, 0.0)

    found = [d for d in lint(off, page=PAGE) if d.code == "OFF_CANVAS"]

    assert found, "nothing was off canvas; the fixture stopped working"
    assert all("glyphs" not in d.message for d in found), [
        d.message for d in found]
    assert all("legend-note" in d.message for d in found), [
        d.message for d in found]


def test_an_unnamed_outlined_block_still_answers_to_its_own_id():
    block = inklet.text("{#c00|WARM} and cold", size=6.0)
    outlined = inklet.outline_text(block)

    found = [d for d in lint(outlined.translated(200.0, 0.0), page=PAGE)
             if d.code == "OFF_CANVAS"]

    assert found
    assert all(block.id in d.message for d in found), [d.message for d in found]


def test_a_single_colour_block_is_untouched_by_the_walk():
    # One colour keeps the outline on the block itself, so there is no carrier
    # to see through and the ordinary naming has to go on working. The words
    # come back too, off the `text` note the outliner leaves behind -- the
    # finding now reads exactly as it would have before the block was
    # outlined, which is the whole point of the note.
    block = inklet.text("plain words", size=6.0).named("caption")
    outlined = inklet.outline_text(block)

    found = [d for d in lint(outlined.translated(200.0, 0.0), page=PAGE)
             if d.code == "OFF_CANVAS"]

    assert [d.message.split(" is ")[0] for d in found] == ["caption 'plain words'"]
    assert [d.message.split(" is ")[0]
            for d in lint(block.translated(200.0, 0.0), page=PAGE)
            if d.code == "OFF_CANVAS"] == ["caption 'plain words'"]
