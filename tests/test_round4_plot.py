"""Round 4: the plot, draw and markup fixes the mouse figure asked for.

Each test here is one line of `figures/mouse_brain.py` that had to be written
the long way round, plus the `fill_rule` item the draw API left unreachable.
The five mouse items were filed as reproductions rather than as guesses, so
these are written the same way: build the thing the figure wanted to build and
measure what it used to get wrong.
"""

from __future__ import annotations

import pytest

import inklet
from inklet.core import (IDENTITY, Diagram, DiagramError, RectPrim, Vec2, group,
                      resolve)
from inklet.links import HEAD_KIND, link, route
from inklet.draw.annotate import LETTER_KIND
from inklet.draw.coords import as_drawn, plot_area
from inklet.plot.key import LEGEND_LABEL_KIND
from inklet.typeset.markup import escape_markup, parse

LINE = [(0.0, 0.0), (10.0, 10.0)]


def legend_words(node) -> list[str]:
    """Every legend row name that reaches the page, markup already read."""
    found = []
    for placed in resolve(as_drawn(node)).values():
        diagram = placed.diagram
        if diagram.kind == LEGEND_LABEL_KIND and diagram.prim is not None:
            text = getattr(diagram.prim, "text", None)
            if text is not None:
                found.append(text)
    return found


def plotted(width: float = 44.0, height: float = 26.0):
    p = inklet.panel(width=width, height=height, x=(0, 10), y=(0, 10))
    p.line(LINE, name="s")
    p.axis("bottom", label="time (s)")
    p.axis("left", label="rate (Hz)")
    return p


# -- 1. a series name is prose ---------------------------------------------

def test_a_series_name_reads_markup() -> None:
    """The reproduction: `ChR2 (//n// = 12)` in the key of `panel_c`."""
    p = plotted()
    p.line(LINE, name="ChR2 (//n// = 12)")
    p.legend()
    assert "ChR2 (n = 12)" in legend_words(p.build())


def test_the_italic_in_a_series_name_reaches_the_page() -> None:
    """Reading the markup is only half of it; the slant has to arrive. The
    figure said `n = 12` in roman before this, which is wrong in every journal
    with a style guide."""
    p = plotted()
    p.line(LINE, name="//n// = 12")
    p.legend()
    fig = inklet.figure(width=70, height=45)
    fig.add(p.build())
    assert 'font-style="italic"' in fig.to_svg()


def test_a_hand_written_legend_reads_markup_too() -> None:
    node = inklet.legend([("C_{2}H_{4}", "#c25703"), ("HCOO^{-}", "#058461")])
    assert legend_words(node) == ["C2H4", "HCOO-"]


def test_markup_false_sets_a_series_name_exactly_as_typed() -> None:
    """For a name that came out of a column header rather than the figure."""
    p = plotted()
    p.line(LINE, name="ChR2 (//n// = 12)")
    p.legend(markup=False)
    assert "ChR2 (//n// = 12)" in legend_words(p.build())


def test_an_unpartnered_delimiter_in_a_name_is_still_itself() -> None:
    """Why the default can be markup at all: `Notch1**` has no closing pair,
    and this grammar hands an unpartnered delimiter back as text. The data
    case that argued for literal names never needed the literal setting."""
    p = plotted()
    p.line(LINE, name="Notch1**")
    p.line(LINE, name="*CO on Pt")
    p.legend()
    assert set(legend_words(p.build())) >= {"Notch1**", "*CO on Pt"}


# -- 2. a column of panels carries a plot area -----------------------------

def test_a_column_of_panels_declares_a_plot_area() -> None:
    """A raster over a PSTH is one figure element and has to say where its
    data region is, or a row places it by its box and its neighbours by
    their areas."""
    pair = inklet.column([plotted(height=16), plotted(height=16)], gap=1.5)
    area = plot_area(pair)
    assert area is not None
    assert area.width == pytest.approx(44.0)


def test_a_columns_area_is_the_union_of_its_members() -> None:
    top, bottom = plotted(height=16), plotted(height=22)
    pair = inklet.column([top, bottom], gap=1.5)
    area = plot_area(pair)
    # Tall enough to hold both areas and the furniture that got between them,
    # and never taller than the box it lives in.
    assert area.height > 16.0 + 22.0
    assert area.height < pair.bbox.height


def test_a_row_is_lined_up_on_areas_too() -> None:
    assert plot_area(inklet.row([plotted(), plotted()])) is not None


def test_a_column_stands_in_a_row_and_keeps_its_letter_on_the_line() -> None:
    """The measurement the item was filed with: `inklet.letters` hung the stacked
    pair's letter a centimetre below its neighbours', because the pair was
    placed by its box. With the areas matched the three letters agree."""
    pair = inklet.column([plotted(height=16), plotted(height=16)], gap=1.5)
    height = plot_area(pair).height
    row = inklet.row(inklet.letters([pair, plotted(height=height),
                               plotted(height=height)]))
    tops = _letter_tops(row)
    assert len(tops) == 3
    assert max(tops) - min(tops) == pytest.approx(0.0, abs=1e-3)


def _letter_tops(node) -> list[float]:
    """Each panel letter's top edge, in `node`'s own frame."""
    out: list[float] = []

    def walk(item, at):
        here = at @ item.transform
        if item.kind == LETTER_KIND and item.prim is not None:
            box = item.local_bbox
            out.append(here.apply(Vec2(box.x0, box.y0)).y)
        for child in item.children:
            walk(child, here)

    walk(node, IDENTITY)
    return out


# -- 3. *** in a caption ----------------------------------------------------

def test_three_asterisks_survive_a_caption_that_also_sets_bold() -> None:
    """The reproduction: `{stars}` back in `mouse_brain.CAPTION`, whose panel
    letters are bold. The `***` used to open a span that ran to `**(b)**`."""
    caption = "**(a)** the first. *** is the threshold. **(b)** the second."
    styled = parse(caption)
    bold = "".join(char for char, mark in zip(styled.text, styled.marks)
                   if mark.bold)
    assert bold == "(a)(b)"
    assert "*** is the threshold." in styled.text


def test_a_run_of_three_or_more_asterisks_is_never_a_delimiter() -> None:
    for run in ("***", "****", "*****"):
        assert parse(f"a {run} b").text == f"a {run} b"


def test_two_asterisks_are_still_bold() -> None:
    styled = parse("**yes**")
    assert styled.text == "yes"
    assert all(mark.bold for mark in styled.marks)


def test_the_backslash_escape_still_reaches_a_single_delimiter() -> None:
    """The run rule wins the common case; the escape is what is left for the
    author who wants one asterisk of a run to be a delimiter after all."""
    assert parse(r"\*\*\* literal").text == "*** literal"
    assert parse(escape_markup("**bold**")).text == "**bold**"


def test_a_bracket_star_and_a_bold_caption_compose() -> None:
    """`p.bracket(..., "***")` beside a caption that sets its letters bold is
    the pair the figure actually draws."""
    p = plotted()
    p.bracket(2, 6, 8.0, text="***")
    assert p.build() is not None
    assert parse("**(e)** the bracket carries ***.").text == \
        "(e) the bracket carries ***."


# -- 4. fit with a builder that also returns links --------------------------

def build_with_links(width: float):
    box = inklet.box(inklet.text("VTA"), pad=1.0)
    label = inklet.text("dopamine neurons")
    node = inklet.hstack([box, label], gap=width / 6.0)
    return node, [inklet.link(box, label, kind="leader")]


def test_fit_hands_back_the_extras_of_the_build_it_kept() -> None:
    node, links = inklet.fit(build_with_links, width=60, with_extras=True)
    kept = {item.id for item in node.walk()}
    assert len(links) == 1
    assert links[0].source.id in kept, "the link names a node of another build"


def test_fit_without_extras_is_unchanged() -> None:
    node = inklet.fit(lambda w: inklet.box(inklet.text("x", width=w)), width=40)
    assert isinstance(node, inklet.Diagram)
    assert node.bbox.width == pytest.approx(40.0, abs=0.05)


def test_fit_says_so_when_the_builder_forgot_the_extras() -> None:
    with pytest.raises(DiagramError, match="Diagram, extras"):
        inklet.fit(lambda w: inklet.text("x"), width=40, with_extras=True)


def test_a_fitted_panel_still_declares_its_plot_area() -> None:
    """`fit` pads the winner to the exact target, and the wrapper used to drop
    the note -- so a fitted panel went into a row by its box."""
    def make(width: float):
        return plotted(width=width).build()

    assert plot_area(inklet.fit(make, width=70)) is not None


# -- 5. a leader's two ends -------------------------------------------------

def test_a_leaders_dot_lands_on_its_source_not_its_target() -> None:
    """What `_leader_points`' docstring now says in words: a callout reads
    `link(region, label)`, the thing being named first. Declared the other way
    round it draws a dot beside the word and an elbow against the drawing,
    which is what the mouse figure's panel (a) did on its first render."""
    region = Diagram(prim=RectPrim(8.0, 8.0))
    label = Diagram(prim=RectPrim(14.0, 4.0)).translated(40.0, -12.0)
    routed = route(link(region, label, kind="leader"),
                   resolve(group([region, label])))
    heads = [item for item in routed.walk() if item.kind == HEAD_KIND]
    assert len(heads) == 1, "a leader wears one head and it is a dot"
    centre = heads[0].bbox.center
    assert abs(centre.x) < 20.0, "the dot sits at the region, not at the word"


# -- 6. fill_rule from the public draw API ----------------------------------

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]
HOLE = [(3, 3), (7, 3), (7, 7), (3, 7)]


@pytest.mark.parametrize("draw", ["path", "polygon", "polyline"])
def test_fill_rule_is_reachable_from_the_public_draw_api(draw: str) -> None:
    node = getattr(inklet, draw)(SQUARE, holes=[HOLE], fill_rule="evenodd",
                              fill="#cccccc", closed=True)
    prim = next(item.prim for item in node.walk() if item.prim is not None)
    assert prim.fill_rule == "evenodd"


def test_an_evenodd_washer_reaches_the_svg() -> None:
    fig = inklet.figure(width=30, height=30)
    fig.add(inklet.polygon(SQUARE, holes=[HOLE], fill_rule="evenodd",
                        fill="#cccccc"))
    assert 'fill-rule="evenodd"' in fig.to_svg()
