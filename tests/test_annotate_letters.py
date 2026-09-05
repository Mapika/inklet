"""What a panel letter hangs off, and what the wrapper round it inherits.

Two claims, both of which the gallery depends on and neither of which was
pinned anywhere:

* the letter rides the panel's **plot area**, not its box, so a row of panels
  whose furniture differs still puts its letters on one line;
* the wrapper `letters` builds inherits the item's notes, minus the ones that
  index children by position -- because this wrapper has two children and the
  item did not.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core.diagram import resolve
from inklet.draw.annotate import CHILD_INDEXED_NOTES, LETTER_KIND

W, H = 21.5, 15.5


def panel(*, legend: bool) -> inklet.Diagram:
    """A gallery-sized panel, optionally carrying a legend above its axes.

    The legend is the whole point: it makes the box taller than its
    neighbour's without moving the plot area a millimetre, which is exactly
    the disagreement `column`, `row` and `facets` line panels up *through*.
    """
    p = inklet.panel(W, H, x=(0.0, 10.0), y=(0.0, 10.0))
    p.line([(0.0, 0.0), (10.0, 10.0)], name="model")
    if legend:
        p.legend(side="top")
    p.axes(x="t / s", y="x")
    return p.build()


def letter_top(node: inklet.Diagram) -> float:
    """The y of the letter's top, in the frame `node` is placed in."""
    places = resolve(node)
    tops = [places[n.id].bbox.y0 for n in node.walk() if n.kind == LETTER_KIND]
    assert len(tops) == 1, tops
    return tops[0]


def test_two_panels_with_different_furniture_letter_on_one_line():
    """The gallery's c/d, e/f and o/p. Off the boxes those three pairs sat
    4.88mm, 4.88mm and 2.61mm apart; off the plot areas they are level."""
    plain, tall = panel(legend=False), panel(legend=True)
    assert tall.bbox.height > plain.bbox.height + 1.0, "the fixture is not a pair"

    row = inklet.facets(inklet.letters([plain, tall]), cols=2, axes=False, gap=5)
    places = resolve(row)
    tops = sorted(places[n.id].bbox.y0 for n in row.walk()
                  if n.kind == LETTER_KIND)

    assert len(tops) == 2
    assert tops[1] - tops[0] == pytest.approx(0.0, abs=1e-6)


def test_the_letter_hangs_off_the_area_and_not_off_the_box():
    """Stated as a measurement rather than as a comparison, so the test says
    which of the two rectangles it is."""
    tall = panel(legend=True)
    area, box = inklet.plot_area(tall), tall.bbox
    assert area.y0 > box.y0 + 1.0, "the fixture's legend stopped making a gap"

    tagged = inklet.letters([tall], pad=1.0)[0]
    top = letter_top(tagged)
    mark = [n for n in tagged.walk() if n.kind == LETTER_KIND][0]

    # No pad in y for an outside letter: `_tagged` spends the pad sideways,
    # where the y-axis label is, and sits the letter directly on the edge.
    assert top == pytest.approx(area.y0 - mark.bbox.height, abs=1e-6)


def test_the_sideways_edge_still_comes_from_the_box():
    """A y-axis label reaches the box's west edge and the letter has to clear
    it, so only the *height* moved to the plot area."""
    p = panel(legend=False)
    tagged = inklet.letters([p], pad=1.0)[0]
    places = resolve(tagged)
    mark = [n for n in tagged.walk() if n.kind == LETTER_KIND][0]

    assert places[mark.id].bbox.x1 <= p.bbox.x0 + 1e-9


def test_the_wrapper_inherits_the_item_s_plot_area():
    """So `facets` lines lettered panels up on the same rectangle the panel
    declared, and a second `letters` pass sees it too."""
    p = panel(legend=True)
    tagged = inklet.letters([p])[0]

    assert inklet.plot_area(tagged) == inklet.plot_area(p)
    assert inklet.plot_area(inklet.letters([tagged])[0]) == inklet.plot_area(p)


def test_the_wrapper_inherits_a_grid_s_gaps():
    """What the hand-written single-note copy used to drop. `carry_notes` is
    core's one implementation and it brings the rest of the notes with it."""
    grid = inklet.grid([inklet.box(str(i)) for i in range(4)], cols=2,
                    col_gap=3.0, row_gap=4.0)
    tagged = inklet.letters([grid])[0]

    assert tagged.notes["col_gap"] == 3.0
    assert tagged.notes["row_gap"] == 4.0
    assert tagged.notes["grid_shape"] == grid.notes["grid_shape"]


def test_the_wrapper_refuses_the_notes_that_index_children():
    """`grid_cells` is one (row, col) per child in `node.children` order, and
    this wrapper's children are (item, letter). Carried across, the crowding
    rule would read the letter as the item's next-door cell and forgive a
    genuinely crowded pair."""
    grid = inklet.grid([inklet.box(str(i)) for i in range(4)], cols=2,
                    col_gap=3.0, row_gap=4.0)
    tagged = inklet.letters([grid])[0]

    assert "grid_cells" in grid.notes
    assert CHILD_INDEXED_NOTES == ("grid_cells",)
    for key in CHILD_INDEXED_NOTES:
        assert key not in tagged.notes


def test_something_that_is_not_a_panel_is_lettered_off_its_box():
    """The fallback, unchanged: a plain diagram declares no area and the
    letter comes off the only rectangle there is."""
    body = inklet.box("panel")
    tagged = inklet.letters([body], pad=1.0)[0]
    mark = [n for n in tagged.walk() if n.kind == LETTER_KIND][0]

    assert inklet.plot_area(body) is None
    assert letter_top(tagged) == pytest.approx(
        body.bbox.y0 - mark.bbox.height, abs=1e-6)


# -- a letter is not a title ----------------------------------------------


def test_a_panel_letter_and_a_panel_title_are_selectable_apart():
    """Round 6 measured the wrong thing because `LETTER_KIND` was `"title"`.

    `[n for n in page.walk() if n.kind == "title"]` returned the letters *and*
    every `p.title(...)` on the page. It now returns only the titles.
    """
    p = inklet.panel(W, H, x=(0.0, 10.0), y=(0.0, 10.0))
    p.line([(0.0, 0.0), (10.0, 10.0)], name="model")
    p.title("condition A")
    tagged = inklet.letters([p.build()])[0]

    letters = [n for n in tagged.walk() if n.kind == LETTER_KIND]
    titles = [n for n in tagged.walk() if n.kind == "title"]
    assert LETTER_KIND != "title"
    assert [n.prim.lines[0].text for n in letters] == ["a"]
    assert [n.prim.lines[0].text for n in titles] == ["condition A"]


def test_the_letter_still_wears_the_panel_title_face():
    """Splitting the kind must not cost the letter its weight or its size.

    The theme's `panel-title` role used to reach the letter through its kind;
    it is written onto the node now, and the emitted style has to be the same
    one -- which is why the corpus moved by nothing but an `id=` prefix.
    """
    theme = inklet.theme("nature")
    face = theme.style_for("panel-title")
    mark = [n for n in inklet.letters([inklet.box("x")])[0].walk()
            if n.kind == LETTER_KIND][0]

    assert mark.style.font_weight == face.font_weight == "bold"
    assert mark.style.font_family == face.font_family
    assert mark.style.font_size == pytest.approx(theme.font_size_large)
    plain = [n for n in inklet.letters([inklet.box("x")], style="lower")[0].walk()
             if n.kind == LETTER_KIND][0]
    assert plain.style.font_weight == "normal"
