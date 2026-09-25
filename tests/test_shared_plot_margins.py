"""Opt-in shared plot furniture across differently labelled grid cells."""

import pytest

import inklet as i
from inklet.core import RectPrim
from inklet.draw.coords import plot_area


def _plots():
    # All data domains agree; axis furniture deliberately differs on every side.
    return (
        i.plot_spec(x=(0, 10), y=(0, 10))
        .line([(0, 0), (10, 10)])
        .axes(x='Elapsed time / s', y='Response / units', key='labels'),
        i.plot_spec(x=(0, 10), y=(0, 10))
        .line([(0, 0), (10, 10)])
        .axes().axis('right', label='Secondary axis', format=lambda value: f'{value:.6f}'),
        # An empty data series still needs the same physical coordinate region.
        i.plot_spec(x=(0, 10), y=(0, 10)).axes(),
        i.plot_spec(x=(0, 10), y=(0, 10))
        .line([(0, 0), (10, 10)])
        .axes().axis('top', label='Elapsed time / s'),
    )


def _grid(factory=i.document, **options):
    doc = factory(width=220, columns=2, **options).letters()
    for index, plot in enumerate(_plots()):
        doc.add(chr(ord('a') + index), plot, row=index // 2, column=index % 2)
    return doc


def _regions(compiled, prefix=''):
    positions = compiled.build()[1]
    result = {}
    for name in ('a', 'b', 'c', 'd'):
        position = positions[f'{prefix}cell-{name}']
        result[name] = plot_area(position.diagram).transform(
            position.world @ position.diagram.transform.inverse())
    return result


def _assert_shared(regions):
    # Every data region has the same height; regions in one column share both
    # vertical grid lines, so they also share their data left and right edges.
    first = next(iter(regions.values()))
    assert first.width > 5 and first.height > 5
    for region in regions.values():
        assert region.height == pytest.approx(first.height, abs=1e-5)
    for top, below in (('a', 'c'), ('b', 'd')):
        assert (regions[top].x0, regions[top].x1) == pytest.approx(
            (regions[below].x0, regions[below].x1), abs=1e-5)


@pytest.mark.parametrize('height', [None, 150])
def test_shared_margins_equalize_data_regions_with_letters_and_empty_series(height):
    compiled = _grid(height=height, share_plot_margins=True).compile()
    regions = _regions(compiled)
    _assert_shared(regions)
    if height is None:
        # The largest top and bottom labels are on different panels. Reserve
        # both instead of subtracting their sum from only one panel's height.
        assert regions['a'].height >= 30 - 1e-5
    margins = []
    for name, region in regions.items():
        cell = compiled.cells[name]
        margins.append((region.x0 - cell.x0, cell.x1 - region.x1,
                        region.y0 - cell.y0, cell.y1 - region.y1))
    assert all(min(margin) >= 0 for margin in margins)
    # Left and right furniture is shared along a column, not across the grid:
    # the right axis on 'b' does not narrow the data in column 0.
    assert margins[2][:2] == pytest.approx(margins[0][:2], abs=1e-5)
    assert margins[3][:2] == pytest.approx(margins[1][:2], abs=1e-5)
    assert margins[1][1] > margins[0][1] + 5
    if height is None:
        # Automatic rows share top and bottom furniture along the row only,
        # so one row's tall labels do not open a gap under every other row.
        assert margins[1][2:] == pytest.approx(margins[0][2:], abs=1e-5)
        assert margins[3][2:] == pytest.approx(margins[2][2:], abs=1e-5)
        assert margins[0][2:] != pytest.approx(margins[2][2:], abs=1e-3)
    else:
        for margin in margins[1:]:
            assert margin[2:] == pytest.approx(margins[0][2:], abs=1e-5)
    assert regions['a'].y0 == pytest.approx(regions['b'].y0)
    assert regions['a'].x0 == pytest.approx(regions['c'].x0)
    assert not any(d.code in ('OFF_CANVAS', 'RULE_FAILED') for d in compiled.diagnostics)


def test_default_layout_remains_identical_to_explicit_false():
    default = _grid()
    explicit = _grid(share_plot_margins=False)
    assert default.share_plot_margins is False
    assert default.compile().to_svg() == explicit.compile().to_svg()
    regions = _regions(default.compile())
    assert abs(regions['a'].width - regions['b'].width) > 5


def test_direct_toggle_invalidates_compilation_and_preserves_previous_snapshot():
    # Unshared cells already align within their column and row tracks; a fixed
    # height is where sharing visibly differs, by equalizing top and bottom.
    doc = _grid(height=150)
    original = doc.compile()
    original_svg = original.to_svg()
    assert doc.compile() is original
    # Direct mutation must participate in the compilation key, independently
    # of configure() clearing the last snapshot.
    doc.share_plot_margins = True
    shared = doc.compile()
    assert shared is not original
    assert doc.compile() is shared
    _assert_shared(_regions(shared))
    assert shared.to_svg() != original_svg
    assert original.to_svg() == original_svg
    doc.configure(share_plot_margins=False)
    assert doc.compile().to_svg() == original_svg


def test_resize_and_label_edit_match_clean_compilation():
    doc = _grid(share_plot_margins=True)
    before = doc.compile()
    doc.configure(width=260, height=180)
    doc['a'].replace('labels', x='Revised elapsed time / s', y='Response / units')
    resized = doc.compile()
    clean = _grid(share_plot_margins=True, height=180)
    clean.configure(width=260)
    clean['a'].replace('labels', x='Revised elapsed time / s', y='Response / units')
    assert resized.to_svg() == clean.compile().to_svg()
    _assert_shared(_regions(resized))
    assert _regions(resized)['a'].width > _regions(before)['a'].width


def test_nested_flag_change_invalidates_parent_and_keeps_child_names_stable():
    inner = _grid(factory=i.subfigure)
    outer = i.document(width=230)
    outer.add('group', inner)
    original = outer.compile()
    before_svg = original.to_svg()
    signature = inner.signature()
    inner.share_plot_margins = True
    assert inner.signature() != signature
    updated = outer.compile()
    assert updated is not original
    assert outer.compile() is updated
    _assert_shared(_regions(updated, 'cell-group/'))
    assert abs(_regions(original, 'cell-group/')['a'].width
               - _regions(original, 'cell-group/')['b'].width) > 5
    assert original.to_svg() == before_svg
    assert not any(d.code in ('OFF_CANVAS', 'RULE_FAILED') for d in updated.diagnostics)


def test_shared_margins_do_not_resize_fixed_diagrams():
    def make(shared):
        doc = _grid(share_plot_margins=shared)
        doc.add('drawing', i.Diagram(prim=RectPrim(25, 12)), row=2, colspan=2)
        return doc.compile()

    original, shared = make(False), make(True)
    for compiled in (original, shared):
        box = compiled.build()[1]['cell-drawing'].bbox
        # Letter decorations add to the cell envelope; the fixed rectangle
        # itself must retain its authored dimensions and world scale.
        rectangles = [p.bbox for p in compiled.build()[1].values()
                      if isinstance(p.diagram.prim, RectPrim)
                      and p.diagram.prim.width == 25 and p.diagram.prim.height == 12]
        assert len(rectangles) == 1
        assert (rectangles[0].width, rectangles[0].height) == pytest.approx((25, 12))
        assert box.width >= 25 and box.height >= 12


def test_shared_margins_respect_unequal_author_selected_column_widths():
    def make(shared):
        doc = i.document(width=220, height=70, columns=(1, 2), share_plot_margins=shared)
        for index, plot in enumerate(_plots()[:2]):
            doc.add(chr(ord('a') + index), plot, row=0, column=index)
        return doc.compile()

    compiled = make(True)
    positions = compiled.build()[1]
    areas = [plot_area(positions[f'cell-{name}'].diagram) for name in ('a', 'b')]
    assert areas[1].width > areas[0].width
    assert areas[0].height == pytest.approx(areas[1].height)
    # The two cells share no vertical grid line, so each keeps its own left
    # and right furniture, exactly as without sharing.
    alone = make(False).build()[1]
    for name, area in zip('ab', areas):
        own = plot_area(alone[f'cell-{name}'].diagram)
        assert (area.x0, area.x1) == pytest.approx((own.x0, own.x1), abs=1e-5)


def _spanned(shared):
    # Twelve tracks with mixed spans, as on a dense journal page. Only 'a'
    # carries a long y label; only 'b' carries wide right-axis furniture.
    doc = i.document(width=183, columns=12, share_plot_margins=shared).letters()

    def plot():
        return i.plot_spec(height=20, x=(0, 10), y=(0, 10)).line([(0, 0), (10, 10)])

    doc.add('a', plot().axes(y='A deliberately long response label / units'),
            row=0, column=0, colspan=6)
    doc.add('b', plot().axes().axis('right', label='Secondary axis',
                                    format=lambda value: f'{value:.6f}'),
            row=0, column=6, colspan=6)
    doc.add('c', plot().axes(), row=1, column=0, colspan=4)
    doc.add('d', plot().axes(), row=1, column=4, colspan=4)
    doc.add('e', plot().axes(), row=1, column=8, colspan=4)
    return doc.compile()


def _areas(compiled, names):
    positions = compiled.build()[1]
    return {name: plot_area(positions[f'cell-{name}'].diagram).transform(
        positions[f'cell-{name}'].world @ positions[f'cell-{name}'].diagram.transform.inverse())
        for name in names}


def test_left_and_right_furniture_is_shared_along_grid_lines_only():
    names = 'abcde'
    shared, alone = _areas(_spanned(True), names), _areas(_spanned(False), names)
    # Cells on the same left grid line align their data left edges, and cells
    # on the same right grid line align their data right edges.
    assert shared['c'].x0 == pytest.approx(shared['a'].x0, abs=1e-5)
    assert shared['e'].x1 == pytest.approx(shared['b'].x1, abs=1e-5)
    assert alone['c'].x0 != pytest.approx(alone['a'].x0, abs=1e-2)
    # A cell that shares no grid line with the long label or the right axis
    # keeps its own furniture instead of reserving theirs.
    assert shared['d'].x0 == pytest.approx(alone['d'].x0, abs=1e-5)
    assert shared['d'].x1 == pytest.approx(alone['d'].x1, abs=1e-5)
    assert shared['d'].width > shared['c'].width


@pytest.mark.parametrize('width, series_count', [(180, 4), (220, 6), (260, 8)])
def test_wrapping_legends_grow_auto_height_without_shrinking_data(width, series_count):
    def make():
        doc = i.document(width=width, columns=2, share_plot_margins=True).letters()
        left = i.plot_spec(height=30, x=(0, 1), y=(0, 1)).axes()
        for index in range(series_count):
            left.line([(0, 0), (1, 1)], name=f'Series {index}')
        left.legend(side='bottom', columns='auto')
        # Sharing this wide right margin makes the other plot's legend wrap
        # more than it did during the initial full-cell-width measurement.
        right = i.plot_spec(height=30, x=(0, 1), y=(0, 1)).axes()
        right.axis('right', label='Right axis', format=lambda value: f'{value:.9f}')
        doc.add('left', left, row=0, column=0)
        doc.add('right', right, row=0, column=1)
        return doc

    def assert_data_height(compiled):
        positions = compiled.build()[1]
        areas = [plot_area(positions[f'cell-{name}'].diagram) for name in ('left', 'right')]
        for area in areas:
            assert area.height == pytest.approx(30, abs=1e-5)
        assert not any(d.code in ('OFF_CANVAS', 'RULE_FAILED') for d in compiled.diagnostics)

    doc = make()
    original = doc.compile()
    original_svg = original.to_svg()
    assert_data_height(original)
    doc.configure(width=width + 60)
    assert_data_height(doc.compile())
    doc.configure(width=width)
    restored = doc.compile()
    assert_data_height(restored)
    assert restored.to_svg() == make().compile().to_svg() == original_svg


@pytest.mark.parametrize('factory', [i.document, i.subfigure, i.Document])
@pytest.mark.parametrize('invalid', [None, 0, 1, 'yes', [], object()])
def test_shared_margin_option_requires_a_boolean(factory, invalid):
    with pytest.raises((TypeError, ValueError), match='share_plot_margins'):
        factory(share_plot_margins=invalid)


def test_invalid_configuration_is_atomic_and_direct_edits_are_revalidated():
    doc = _grid(share_plot_margins=True)
    compiled = doc.compile()
    with pytest.raises((TypeError, ValueError), match='share_plot_margins'):
        doc.configure(width=260, share_plot_margins=1)
    assert doc.width == 220
    assert doc.share_plot_margins is True
    assert doc.compile() is compiled
    doc.share_plot_margins = 'yes'
    with pytest.raises((TypeError, ValueError), match='share_plot_margins'):
        doc.compile()


def test_all_shares_left_and_right_furniture_across_the_grid():
    # Small multiples need one physical scale: 'all' keeps the whole-grid rule.
    for height in (None, 150):
        regions = _regions(_grid(height=height, share_plot_margins='all').compile())
        first = regions['a']
        for region in regions.values():
            assert (region.width, region.height) == pytest.approx(
                (first.width, first.height), abs=1e-5)
    spanned = _areas(_spanned('all'), 'abcde')
    assert spanned['d'].width == pytest.approx(spanned['c'].width, abs=1e-5)


def _rows(shared):
    # Rows with their own authored data heights, as on a dense page, and
    # different furniture in each column.
    doc = i.document(width=183, columns=12, share_plot_margins=shared).letters()

    def plot(height):
        return i.plot_spec(height=height, x=(0, 10), y=(0, 10)).line([(0, 0), (10, 10)])

    doc.add('a', plot(20).axes(y='Response').axis(
        'left', format=lambda value: f'{value:.4f}'), row=0, column=0, colspan=6)
    doc.add('b', plot(20).axes(), row=0, column=6, colspan=6)
    doc.add('c', plot(34).axes(), row=1, column=0, colspan=4)
    doc.add('d', plot(34).axes().axis('right', label='Secondary axis'),
            row=1, column=4, colspan=8)
    return doc.compile()


def test_true_keeps_row_heights_while_sharing_grid_lines():
    names = 'abcd'
    shared, alone = _areas(_rows(True), names), _areas(_rows(False), names)
    for name, height in zip(names, (20, 20, 34, 34)):
        assert shared[name].height == pytest.approx(height, abs=1e-5)
        assert alone[name].height == pytest.approx(height, abs=1e-5)
    # Left and right edges still line up along the shared grid lines.
    assert shared['c'].x0 == pytest.approx(shared['a'].x0, abs=1e-5)
    assert shared['d'].x1 == pytest.approx(shared['b'].x1, abs=1e-5)
    assert alone['c'].x0 != pytest.approx(alone['a'].x0, abs=1e-2)
    assert shared['a'].y0 == pytest.approx(shared['b'].y0, abs=1e-5)
    assert shared['c'].y0 == pytest.approx(shared['d'].y0, abs=1e-5)


def test_all_still_gives_every_plot_the_tallest_data_height():
    areas = _areas(_rows('all'), 'abcd')
    for area in areas.values():
        assert area.height == pytest.approx(34, abs=1e-5)
