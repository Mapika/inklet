"""What round 3's showcase pass promised, held to it.

Three of these are contract tests for behaviour nothing else pins down: that a
stack remembers the gap it was given, that a restyle carries whatever a builder
stamped on a node, and that eight series get eight colours in every theme even
where the published palette is only seven long. The fourth is the standing
measurement `test_themes` keeps for contrast, extended to the case where
neither end of a theme's own range is readable on the fill.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.draw.annotate import LETTER_KIND
from inklet.figure import apply_theme
from inklet.themes import THEMES, contrast_ratio


# -- a stack records its gap ------------------------------------------------

def notes_of(node):
    return getattr(node, "notes", {})


def test_stack_records_the_gap_it_was_given():
    node = inklet.vstack([inklet.box("a"), inklet.box("b")], gap=3.25)
    assert notes_of(node).get("gap") == pytest.approx(3.25)


def test_stack_records_the_axis_it_ran_along():
    down = inklet.vstack([inklet.box("a"), inklet.box("b")], gap=2.0)
    across = inklet.hstack([inklet.box("a"), inklet.box("b")], gap=2.0)
    assert notes_of(down)["gap_axis"].y == pytest.approx(1.0)
    assert notes_of(across)["gap_axis"].x == pytest.approx(1.0)


def test_a_named_gap_is_recorded_as_the_millimetres_it_resolved_to():
    """The finding a rule wants is "0.5mm apart", not "the author said 2xs"."""
    theme = inklet.theme("nature")
    node = inklet.hstack([inklet.box("a"), inklet.box("b")], gap=theme.gap("m"))
    assert notes_of(node).get("gap") == pytest.approx(theme.gap("m"))


def test_a_grid_records_the_tighter_of_its_two_gaps():
    """A crowding finding is measured against the tightest pair on the page."""
    node = inklet.grid([inklet.box(c) for c in "abcd"], cols=2,
                    row_gap=2.0, col_gap=8.0)
    assert notes_of(node).get("gap") == pytest.approx(2.0)


def test_the_gap_survives_a_restyle():
    """`apply_theme` rebuilds every node with `dataclasses.replace`; the note
    has to come through it and through the `build` after it."""
    node = inklet.vstack([inklet.box("a"), inklet.box("b")], gap=4.0)
    restyled = apply_theme(node, inklet.theme("slides"))
    assert notes_of(restyled).get("gap") == pytest.approx(4.0)


def test_the_gap_is_still_there_after_a_figure_builds():
    """The tree a rule sees is the built one."""
    fig = inklet.figure(width="80mm")
    fig.add(inklet.vstack([inklet.box("a"), inklet.box("b")], gap=4.0))
    found = [n for n in fig.build()[0].walk()
             if getattr(n, "notes", {}).get("gap") == 4.0]
    assert found


def test_a_restyle_carries_an_annotation_it_has_never_heard_of():
    """Carried by inspection, not by name -- the next annotation needs no edit
    to `figure.apply_theme`."""
    node = inklet.vstack([inklet.box("a")], gap=1.0)
    object.__setattr__(node, "invented_later", 17)
    restyled = apply_theme(node, inklet.theme("notebook"))
    assert getattr(restyled, "invented_later", None) == 17


def test_the_annotation_does_not_make_two_equal_stacks_unequal():
    """A plain attribute, not a field: `Diagram` keeps the shape core froze."""
    one = inklet.vstack([inklet.box("a"), inklet.box("b")], gap=2.0)
    two = inklet.vstack([inklet.box("a"), inklet.box("b")], gap=2.0)
    assert one.bbox == two.bbox


# -- eight series, eight colours --------------------------------------------

@pytest.mark.parametrize("name", sorted(THEMES))
def test_eight_series_get_eight_distinct_colours(name):
    """Tol's bright scheme is seven long. The eighth series used to be the
    first one again, which names two things with one swatch."""
    theme = THEMES[name]
    shades = [theme.color(i) for i in range(8)]
    assert len(set(shades)) == 8, shades


@pytest.mark.parametrize("name", sorted(THEMES))
def test_the_palette_itself_is_untouched(name):
    """Overflow shading must not reach back and edit a cited palette."""
    theme = THEMES[name]
    assert [theme.color(i) for i in range(len(theme.palette))] == \
        list(theme.palette)


def test_overflow_is_a_shade_of_the_colour_it_wraps_to():
    """The hue is kept, so a reader who separates the base colours separates
    these too -- the overflow reads as "series 1 again, lighter", which is a
    truer picture of an eight-category chart on a seven-colour scheme."""
    theme = inklet.theme("slides")
    size = len(theme.palette)
    base, over = theme.color(0), theme.color(size)
    assert base != over
    # Same hue family: the two differ mostly in lightness, not in channel order.
    def order(hex_color):
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return sorted(range(3), key=[r, g, b].__getitem__)
    assert order(base) == order(over)


def test_negative_indices_still_read_from_the_end():
    theme = inklet.theme("nature")
    assert theme.color(-1) == theme.palette[-1]


# -- text on colour ----------------------------------------------------------

@pytest.mark.parametrize("name", sorted(THEMES))
def test_text_on_any_palette_fill_clears_aa(name):
    """`text_on` used to return the better of ink and paper even when neither
    passed. Tol's rose under the notebook theme is the case: 4.3:1 on ink,
    3.5:1 on paper, and now 4.5:1 on a walked ink."""
    theme = THEMES[name]
    for fill in theme.palette:
        ratio = contrast_ratio(theme.text_on(fill), fill)
        assert ratio >= 4.5 - 1e-9, (name, fill, ratio)


@pytest.mark.parametrize("name", sorted(THEMES))
def test_text_on_still_returns_plain_ink_where_plain_ink_works(name):
    """The common case must be byte-identical: this is what keeps the change
    off the corpus."""
    theme = THEMES[name]
    assert theme.text_on(theme.paper) == theme.ink


# -- markup in a link label --------------------------------------------------

def test_a_link_label_can_name_a_theme_colour():
    """`{accent|sample}` on a connector is a colour span, not five characters
    of punctuation -- `Figure.link` has to hand the shaper the theme's table."""
    theme = inklet.theme("nature")
    fig = inklet.figure(width="80mm", theme=theme)
    a, b = inklet.box("a"), inklet.box("b")
    fig.add(inklet.hstack([a, b], gap=20.0))
    fig.link(a, b, label="{accent|sample}")
    svg = fig.to_svg()
    assert theme.accent in svg
    assert "{accent|" not in svg


def test_a_plain_link_label_is_unaffected():
    fig = inklet.figure(width="80mm")
    a, b = inklet.box("a"), inklet.box("b")
    fig.add(inklet.hstack([a, b], gap=20.0))
    fig.link(a, b, label="plain")
    assert "{" not in fig.to_svg()


# -- the three showcase figures ---------------------------------------------

@pytest.mark.parametrize("module", ["showcase_process", "showcase_season",
                                    "showcase_part"])
def test_showcase_figures_lint_clean(module):
    """These are the figures the README points a new reader at. A diagnostic in
    one of them is a diagnostic in the first thing anybody sees."""
    import importlib
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    fig = importlib.import_module(f"figures.{module}").fig
    assert not [d for d in fig.lint() if d.severity != "info"], fig.report()


def test_process_link_labels_do_not_cover_the_boxes_they_connect():
    """The eluate plate erased a border even though the figure linted clean."""
    import runpy
    from pathlib import Path

    from inklet.links import LABEL_KIND, LINK_KIND

    source = Path(__file__).resolve().parent.parent / "figures" / "showcase_process.py"
    fig = runpy.run_path(str(source))["fig"]
    root, placements = fig.build()
    checked = 0
    for node in root.walk():
        if node.kind != LINK_KIND:
            continue
        for label in node.children:
            if label.kind != LABEL_KIND:
                continue
            plate = placements[label.id].bbox
            for endpoint in node.attached_to:
                target = placements[endpoint].bbox
                assert plate.overlap(target) is None, (plate, target)
            checked += 1
    assert checked == 9


@pytest.mark.parametrize("module", ["showcase_process", "showcase_season",
                                    "showcase_part"])
def test_showcase_figures_render_byte_identically_twice(module):
    import importlib
    import sys
    from pathlib import Path

    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    fig = importlib.import_module(f"figures.{module}").fig
    assert fig.to_svg() == fig.to_svg()


# -- a role could be italic, and deliberately is not -------------------------

def test_a_role_table_can_carry_font_style():
    """`Style.font_style` is live end to end (typeset measures it, render
    emits it). Nothing in `themes/` has to change for a theme to use it -- a
    role is a `Style` and `Style` has the field -- and this pins that, because
    the capability is easy to lose to a role table that filters its keywords.

    No *shipped* role sets it, on purpose: a journal caption is roman, an axis
    label is roman, and italic in a figure means something specific -- a
    variable, a species name, an emphasis the author chose. That is what
    `//markup//` is for, and a role that italicised a whole class of text would
    leave `//x//` inside it with nothing to say.
    """
    import dataclasses

    from inklet.core.style import Style
    from inklet.themes.theme import Theme

    assert "font_style" in {f.name for f in dataclasses.fields(Style)}

    real = Theme.style_for
    try:
        Theme.style_for = lambda self, role: (
            dataclasses.replace(real(self, role), font_style="italic")
            if role == "emphasis" else real(self, role))
        fig = inklet.figure(width="60mm")
        fig.add(inklet.Diagram(prim=inklet.shape("hello"), kind="emphasis"))
        assert "italic" in fig.to_svg()
    finally:
        Theme.style_for = real


@pytest.mark.parametrize("name", sorted(THEMES))
def test_no_shipped_role_is_italic(name):
    from inklet.themes import ROLES

    theme = THEMES[name]
    italic = [r for r in ROLES if theme.style_for(r).font_style == "italic"]
    assert italic == [], italic


# -- panel letters share a baseline ------------------------------------------

def _panel(legend: bool):
    p = inklet.panel(40, 20, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], name="s")
    p.axes(x="x", y="y")
    if legend:
        p.legend(side="top")
    return p


def _letter_tops(node):
    from inklet.core import resolve

    places = resolve(node)
    return [round(places[c.id].bbox.y0, 6) for c in node.walk()
            if str(c.kind) == LETTER_KIND and c.prim is not None]


def test_letters_on_faceted_panels_land_on_one_line():
    """A legend across the top makes one panel's *box* 4.9mm taller than its
    neighbour's while their plot areas stay the same size. `facets` aligns the
    areas, so a letter hung off the box used to ride 4.9mm higher -- two
    letters on two lines, which is the first thing a reader notices."""
    grid = inklet.facets(inklet.letters([_panel(False), _panel(True)]), cols=2,
                      axes=False)
    tops = _letter_tops(grid)
    assert len(tops) == 2 and tops[0] == tops[1]


def test_the_letter_sits_at_the_top_of_the_plot_area():
    """Not at the top of the box: the box includes the legend, and the plot
    area is the line every panel in the row agrees on."""
    from inklet.core import resolve

    panel = _panel(True)
    tagged = inklet.letters([panel])[0]
    places = resolve(tagged)
    area = tagged.notes["plot_area"]
    letter = [places[c.id].bbox for c in tagged.walk()
              if str(c.kind) == LETTER_KIND and c.prim is not None][0]
    # Its baseline sits *on* the area's top edge, the way an outside letter
    # sits on any edge -- and well above the box top, which the legend owns.
    assert letter.y1 == pytest.approx(area.y0)
    assert letter.y1 > tagged.bbox.y0 + 2.0


def test_a_lettered_panel_still_declares_its_plot_area():
    """Whatever composes these next has to be able to align them, and the
    wrapper's own box is the thing the letter just changed the shape of."""
    panel = _panel(True)
    tagged = inklet.letters([panel])[0]
    assert tagged.notes["plot_area"].width == pytest.approx(40.0)
    assert tagged.notes["plot_area"].height == pytest.approx(20.0)


def test_a_plain_diagram_still_gets_its_letter_on_the_box():
    """No plot area, no change: `letters` over boxes is the old behaviour."""
    box = inklet.box("a")
    tagged = inklet.letters([box])[0]
    assert tagged.bbox.y0 < box.bbox.y0


def test_the_letter_column_is_still_outside_the_whole_panel():
    """Height comes from the plot area; the sideways edge must not, or the
    letter lands on top of the y-axis label."""
    from inklet.core import resolve

    panel = _panel(False)
    tagged = inklet.letters([panel])[0]
    places = resolve(tagged)
    built = places[panel.build().id].bbox
    letter = [places[c.id].bbox for c in tagged.walk()
              if str(c.kind) == LETTER_KIND and c.prim is not None][0]
    assert letter.x1 <= built.x0
