"""Regression tests for sizes and positions a document must not change silently.

Each test names the issue it guards. Geometry is measured from the placed
cells, never from pixels.
"""
import numpy as np
import pytest

import inklet as i
from inklet.core.prims import TextPrim
from inklet.document.errors import LayoutError
from inklet.draw.coords import plot_area


def _areas(figure):
    """{cell name: its plot's data area in page millimetres} for placed plots."""
    found = {}

    def walk(node):
        if node.kind == 'document-cell':
            area = plot_area(node)
            if area is not None:
                found[node.name] = area
        for child in node.children:
            walk(child)

    walk(figure.root)
    return found


def _codes(figure):
    return [d.code for d in figure.diagnostics]


def _texts(figure):
    out = set()

    def walk(node):
        if isinstance(node.prim, TextPrim):
            out.update(line.text for line in node.prim.lines)
        for child in node.children:
            walk(child)

    walk(figure.root)
    return out


def _strips(margin, labels, row_gap=3):
    doc = i.preset("scientific.nature", format="double-column").document(
        columns=1, row_gap=row_gap, margin=margin, share_plot_margins=True)
    for k, label in enumerate(labels):
        s = i.plot_spec(148, 8.5, x=(0, 1), y=(0, 1))
        s.line([(0, 0), (1, 1)])
        s.axes(x=None, y=label)
        doc.add(f"s{k}", s, row=k)
    return doc


# -- R1: a y-axis title longer than its plot keeps the plot's height ----------

def test_long_axis_title_keeps_the_authored_plot_height():
    # The issue's repro: the first strip's title is 21 mm long on an 8.5 mm plot.
    figure = _strips(4, ["Added depth (ppm)", None, None]).compile()
    heights = {name: round(area.height, 3) for name, area in _areas(figure).items()}
    assert heights == {'s0': 8.5, 's1': 8.5, 's2': 8.5}


def test_stacked_strips_share_one_scale_with_a_long_title():
    figure = _strips(12, ["Added depth (ppm)", "Added depth (ppm)", None]).compile()
    areas = _areas(figure)
    assert {round(a.height, 3) for a in areas.values()} == {8.5}
    assert len({round(a.width, 3) for a in areas.values()}) == 1


def test_title_that_overhangs_without_colliding_is_silent():
    # With a page margin tall enough for the title, nothing is hit: no diagnostic.
    figure = _strips(12, ["Added depth (ppm)", None, None]).compile()
    assert 'AXIS_TITLE_OVERHANG' not in _codes(figure)


def test_title_that_collides_with_the_next_strip_is_reported():
    # Each title overhangs its strip by 6.3 mm, and the 3 mm row gap cannot hold both.
    figure = _strips(12, ["Added depth (ppm)", "Added depth (ppm)", None]).compile()
    found = [d for d in figure.diagnostics if d.code == 'AXIS_TITLE_OVERHANG']
    assert found, figure.report()
    message = found[0].message
    assert "'s0'" in message and '8.5 mm' in message and '21.1 mm' in message
    assert 'keeps its 8.5 mm' in message
    assert {round(a.height, 3) for a in _areas(figure).values()} == {8.5}


def test_title_past_the_page_edge_is_reported_and_plot_still_honoured():
    figure = _strips(4, ["Added depth (ppm)", None, None]).compile()
    assert any(d.code == 'AXIS_TITLE_OVERHANG' and 'page edge' in d.message
               for d in figure.diagnostics)
    assert round(_areas(figure)['s0'].height, 3) == 8.5


# -- katrin_2022#5: a plot's authored width is honoured when it fits ----------

def _pair(main_width, side_width, page, columns, gap=6):
    main = i.plot_spec(main_width, 50, x=(0, 1), y=(0, 1))
    main.axes()
    right = i.plot_spec(side_width, 50, x=(0, 1), y=(0, 1))
    right.line([(0, 0), (1, 1)])
    doc = i.preset("scientific.nature", format="single-column").document(
        width=page, columns=columns, gap=gap)
    doc.add("m", main, row=0, column=0)
    doc.add("r", right, row=0, column=1)
    return doc.compile()


def test_authored_plot_width_is_honoured_when_the_row_has_room():
    figure = _pair(60, 14, page=180, columns=2)
    areas = _areas(figure)
    # Equal columns give each 76 mm or so here: the plot is at least its 60 mm.
    assert areas['m'].width >= 60 - .01
    assert areas['r'].width >= 14 - .01
    assert 'PLOT_WIDTH_OVERRIDDEN' not in _codes(figure)


def test_authored_plot_width_that_does_not_fit_is_reported():
    # Columns of 37.5 mm on an 89 mm page cannot hold 60 mm of data plus furniture.
    figure = _pair(60, 14, page=89, columns=2)
    found = [d for d in figure.diagnostics if d.code == 'PLOT_WIDTH_OVERRIDDEN']
    assert len(found) == 1, figure.report()
    assert "'m'" in found[0].message and '60.0 mm' in found[0].message
    assert 'columns=' in found[0].hint
    assert _areas(figure)['m'].width < 60


def test_a_few_millimetres_trimmed_by_tick_labels_are_not_reported():
    # A grid's nominal width loses a little to each cell's own tick labels; that
    # is layout, not a broken promise, so only a loss over 15% is reported.
    figure = _pair(40, 30, page=89, columns=2)
    drawn = _areas(figure)['m'].width
    assert 40*.85 <= drawn < 40, drawn
    assert 'PLOT_WIDTH_OVERRIDDEN' not in _codes(figure)


def test_a_width_a_little_too_wide_gives_way_only_as_far_as_it_must():
    # Authored widths that do not fit used to be dropped outright, so a plot
    # authored 40 mm was drawn at 31 mm while one authored 38 mm kept 38 mm.
    drawn = [_areas(_pair(w, 30, page=89, columns=2))['m'].width for w in (36, 38, 40, 45)]
    assert drawn == sorted(drawn), drawn
    assert drawn[2] > 38, drawn


def test_plot_width_left_to_its_default_does_not_bind():
    main = i.plot_spec(height=50, x=(0, 1), y=(0, 1))
    main.axes()
    doc = i.preset("scientific.nature", format="single-column").document(width=89, columns=2)
    doc.add("m", main, row=0, column=0)
    right = i.plot_spec(height=50, x=(0, 1), y=(0, 1))
    right.line([(0, 0), (1, 1)])
    doc.add("r", right, row=0, column=1)
    figure = doc.compile()
    assert 'PLOT_WIDTH_OVERRIDDEN' not in _codes(figure)


# -- katrin_2022#2: bars wider than their axis are named ----------------------

def _bars(width):
    ys = np.linspace(18573.57, 18573.80, 42)
    plot = i.plot_spec(14, 50, x=(0, 10), y=(ys[0] - 0.003, ys[-1] + 0.003))
    plot.bars(ys, np.ones_like(ys) * 5, width=width, orient="h")
    doc = i.preset("scientific.nature", format="single-column").document()
    doc.add("a", plot)
    return doc.compile(), ys


def test_horizontal_bars_wider_than_the_axis_are_named_with_their_units():
    figure, _ = _bars(1.0)
    found = [d for d in figure.diagnostics if d.code == 'BAR_WIDTH_OUT_OF_SCALE']
    assert len(found) == 1, figure.report()
    assert 'width=1' in found[0].message and 'y data units' in found[0].message
    assert 'y axis' in found[0].message
    # The data area keeps its authored height; the page is what grows.
    assert round(_areas(figure)['a'].height, 3) == 50


def test_horizontal_bars_at_the_bin_pitch_are_not_reported():
    _, ys = _bars(1.0)
    figure, _ = _bars(float(ys[1] - ys[0]))
    assert 'BAR_WIDTH_OUT_OF_SCALE' not in _codes(figure)


# -- marek_bwas_2022#2: a cell added without row= under a free column --------

def _cell_plot():
    plot = i.plot_spec(30, 20, x=(0, 1), y=(0, 1))
    plot.line([(0, 0), (1, 1)])
    return plot


def test_omitted_row_under_a_free_column_is_refused_with_both_rows():
    # The reported page was 434 mm tall: c1 silently went to row 1.
    sub = i.subfigure(columns=2, gap=3)
    sub.add("c0", _cell_plot(), column=0)
    with pytest.raises(LayoutError, match=r"Pass row=0 .* row=1"):
        sub.add("c1", _cell_plot(), column=1)
    assert [c.name for c in sub._cells] == ["c0"]


def test_explicit_row_places_a_cell_beside_its_neighbour():
    sub = i.subfigure(columns=2, gap=3)
    sub.add("c0", _cell_plot(), column=0)
    sub.add("c1", _cell_plot(), row=0, column=1)
    assert {c.name: (c.row, c.column) for c in sub._cells} == {'c0': (0, 0), 'c1': (0, 1)}


def test_omitted_row_appends_below_when_the_column_is_taken():
    sub = i.subfigure(columns=2, gap=3)
    sub.add("a", _cell_plot(), row=0, column=0)
    sub.add("b", _cell_plot(), row=0, column=1)
    sub.add("c", _cell_plot(), column=0)
    assert {c.name: (c.row, c.column) for c in sub._cells} == {
        'a': (0, 0), 'b': (0, 1), 'c': (1, 0)}


def test_the_first_cell_without_row_is_in_row_zero():
    doc = i.document(columns=2)
    doc.add('a', _cell_plot(), column=1)
    assert (doc._cells[0].row, doc._cells[0].column) == (0, 1)


def test_explicit_row_is_still_exact():
    doc = i.document(columns=2)
    doc.add('a', _cell_plot(), row=3, column=1)
    assert (doc._cells[0].row, doc._cells[0].column) == (3, 1)


# -- marek_bwas_2022#1: panel letters by cell name ----------------------------

def _lettered(names=None, **options):
    doc = i.preset("scientific.nature", format="double-column").document(columns=2)
    for name, row, col in [("a", 0, 0), ("b", 0, 1), ("e", 1, 0), ("f", 1, 1)]:
        plot = i.plot_spec(30, 20, x=(0, 1), y=(0, 1))
        plot.line([(0, 0), (1, 1)])
        doc.add(name, plot, row=row, column=col)
    if names is None:
        doc.letters(**options)
    else:
        doc.letters(names, **options)
    return doc.compile()


def test_letters_can_be_set_by_cell_name_and_skip_letters():
    figure = _lettered({"a": "a", "b": "b", "e": "e", "f": "f"})
    letters = {t for t in _texts(figure) if len(t) == 1 and t.isalpha()}
    assert letters == {'a', 'b', 'e', 'f'}


def test_unnamed_cells_take_the_next_free_letter():
    figure = _lettered({"b": "b"}, start="a")
    letters = {t for t in _texts(figure) if len(t) == 1 and t.isalpha()}
    # 'a', 'e' and 'f' are unnamed: they take a, c and d, skipping the named 'b'.
    assert letters == {'a', 'b', 'c', 'd'}


def test_default_letters_are_unchanged():
    figure = _lettered(start="a")
    letters = {t for t in _texts(figure) if len(t) == 1 and t.isalpha()}
    assert letters == {'a', 'b', 'c', 'd'}


def test_letters_name_a_cell_that_does_not_exist():
    doc = i.document(columns=1)
    plot = i.plot_spec(30, 20, x=(0, 1), y=(0, 1))
    plot.line([(0, 0), (1, 1)])
    doc.add('a', plot)
    doc.letters({'nope': 'x'})
    with pytest.raises(Exception, match="'nope'"):
        doc.compile()


def test_letters_must_be_single_letters_and_distinct():
    doc = i.document()
    with pytest.raises(ValueError, match='one character'):
        doc.letters({'a': 'ab'})
    with pytest.raises(ValueError, match='given to both'):
        doc.letters({'a': 'x', 'b': 'x'})


# -- who_excess_2023#3: a cell name with a space is refused clearly ----------

def test_cell_name_with_a_space_is_refused_with_the_reason():
    doc = i.document()
    with pytest.raises(ValueError, match='African region') as error:
        doc.add('African region', i.plot_spec(30, 20))
    assert 'title()' in str(error.value)


def test_a_plot_alone_in_its_row_is_capped_by_the_page_without_a_report():
    # plot_spec(89, ...) on an 89 mm page asks for "as wide as it goes"; the
    # page, not a column split, limits it, so there is nothing to report.
    plot = i.plot_spec(89, 50, x=(0, 1), y=(0, 1))
    plot.line([(0, 0), (1, 1)]).axes(x="x", y="y")
    doc = i.preset("scientific.nature", format="single-column").document()
    doc.add("only", plot)
    figure = doc.compile()
    assert _areas(figure)['only'].width < 89
    assert 'PLOT_WIDTH_OVERRIDDEN' not in _codes(figure)
