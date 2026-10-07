"""Plots that keep an exact data aspect: `plot_spec(aspect='equal')` and numbers."""
import pytest

import inklet as i
from inklet.core import resolve
from inklet.draw.coords import plot_area
from inklet.plot.scale import log

# A streets-like map in a 0..20 x 0..10 unit space: one unit must be the same
# length on both axes for the map to be a map.
STREETS = [[(0, 2), (20, 2)], [(3, 0), (3, 10)], [(0, 9), (15, 1)], [(5, 10), (18, 4)],
           [(12, 0), (20, 8)]]
# (x, y) fraction of the slack that lies before the plot, for each compass align.
FRACTIONS = {'center': (.5, .5), 'n': (.5, 0), 's': (.5, 1), 'e': (1, .5), 'w': (0, .5),
             'nw': (0, 0), 'ne': (1, 0), 'sw': (0, 1), 'se': (1, 1)}


def _map(**options):
    p = i.plot_spec(**options, x=(0, 20), y=(0, 10))
    for seg in STREETS:
        p.line(seg, stroke_width=0.2)
    return p.axes()


def _page(position, rect):
    return rect.transform(position.world @ position.diagram.transform.inverse())


def _areas(compiled):
    """Data regions in page millimetres, keyed by cell name."""
    positions = compiled.build()[1]
    return {name: _page(positions[f'cell-{name}'], plot_area(positions[f'cell-{name}'].diagram))
            for name in compiled.metadata['cells']}


def _ink(compiled):
    """Each cell's whole plot, furniture included, in page millimetres."""
    positions = compiled.build()[1]
    return {name: _page(positions[f'cell-{name}'], positions[f'cell-{name}'].diagram.bbox)
            for name in compiled.metadata['cells']}


def _compile(width=120, *, height=None, aspect=None, **options):
    doc = i.document(width=width)
    doc.add('a', _map(**({} if height is None else {'height': height}),
                      **({} if aspect is None else {'aspect': aspect}), **options))
    return doc.compile()


# -- authoring -----------------------------------------------------------------

def test_aspect_is_recorded_validated_and_cleared():
    assert i.plot_spec(10, 10, aspect='equal').options['aspect'] == 'equal'
    assert i.plot_spec(10, 10, aspect=2).options['aspect'] == 2.0
    assert 'aspect' not in i.plot_spec(10, 10, aspect=None).options
    plot = i.plot_spec(10, 10, aspect=.5)
    assert 'aspect' not in plot.configure(aspect=None).options
    assert plot.configure(aspect='equal').options['aspect'] == 'equal'
    assert plot.copy().options['aspect'] == 'equal'


@pytest.mark.parametrize('bad', ['square', 0, -1, float('nan'), float('inf'), True, [1]])
def test_aspect_rejects_anything_but_equal_or_a_positive_number(bad):
    with pytest.raises(ValueError, match='aspect must be'):
        i.plot_spec(10, 10, aspect=bad)
    with pytest.raises(ValueError, match='aspect must be'):
        i.plot_spec(10, 10).configure(aspect=bad)


def test_aspect_is_part_of_the_recipe_so_editing_it_recompiles():
    doc = i.document(width=120)
    plot = _map(aspect='equal')
    doc.add('a', plot)
    first = doc.compile().to_svg()
    # 'equal' here is 0.5 (the spans are 20 by 10), so a different number is needed.
    plot.configure(aspect=.7)
    assert doc.compile().to_svg() != first


def test_aspect_compiles_byte_identical_twice():
    assert _compile(aspect='equal', height=40).to_svg() == _compile(aspect='equal', height=40).to_svg()


# -- equal scale ---------------------------------------------------------------

def test_equal_gives_one_unit_the_same_length_on_both_axes():
    # Streets in a 0..20 x 0..10 space, in a single column, with axes.
    doc = i.publication('single-column').document()
    doc.add('map', _map(width=100, height=50, aspect='equal'))
    area = _areas(doc.compile())['map']
    per_x, per_y = area.width / 20, area.height / 10
    assert per_x == pytest.approx(per_y, abs=0.01)
    assert area.height <= 50 + 1e-9 and area.width < 100


def test_the_authored_height_caps_an_equal_map_and_the_width_is_centred():
    compiled = _compile(width=180, aspect='equal', height=50)
    area = _areas(compiled)['a']
    assert area.height == pytest.approx(50, abs=1e-6)
    assert area.width == pytest.approx(100, abs=1e-6)
    ink, cell = _ink(compiled)['a'], compiled.metadata['cells']['a']
    assert ink.x0 - cell['x'] == pytest.approx(cell['x'] + cell['width'] - ink.x1, abs=0.01)


def test_equal_scale_holds_with_auto_domains():
    # The domains come from the marks; the equal scale must hold on them.
    p = i.plot_spec(height=40, x='auto', y='auto', aspect='equal')
    for seg in STREETS:
        p.line(seg)
    doc = i.document(width=160)
    doc.add('a', p.axes())
    area = _areas(doc.compile())['a']
    assert area.width / area.height == pytest.approx(2.0, abs=1e-6)


def test_numeric_aspect_is_height_over_width_of_the_data_region():
    area = _areas(_compile(width=180, aspect=0.8, height=60))['a']
    assert area.height / area.width == pytest.approx(0.8, abs=1e-9)
    assert area.height == pytest.approx(60, abs=1e-6)


def test_numeric_aspect_on_a_narrow_cell_is_limited_by_width():
    compiled = _compile(width=70, aspect=0.5, height=60)
    area = _areas(compiled)['a']
    assert area.height / area.width == pytest.approx(0.5, abs=1e-9)
    cell = compiled.metadata['cells']['a']
    assert area.x1 <= cell['x'] + cell['width'] + 1e-6


def test_natural_height_follows_the_fitted_region_in_a_narrow_column():
    # A narrow column makes the map shorter than its authored height: the row
    # needs only the map and its furniture, not the 80 mm authored.
    compiled = _compile(width=60, aspect='equal', height=80)
    area = _areas(compiled)['a']
    cell = compiled.metadata['cells']['a']
    assert area.height / area.width == pytest.approx(0.5, abs=1e-9)
    assert cell['height'] < 80 and cell['height'] - area.height < 12


# -- align ----------------------------------------------------------------------

@pytest.mark.parametrize('align', sorted(FRACTIONS))
def test_align_puts_the_whole_plot_where_its_compass_point_says(align):
    doc = i.document(width=180)
    doc.add('a', _map(height=50, aspect='equal'), align=align)
    compiled = doc.compile()
    ink, cell = _ink(compiled)['a'], compiled.metadata['cells']['a']
    fx, fy = FRACTIONS[align]
    assert ink.x0 - cell['x'] == pytest.approx(fx * (cell['width'] - ink.width), abs=0.01)
    assert ink.y0 - cell['y'] == pytest.approx(fy * (cell['height'] - ink.height), abs=0.01)


def test_align_moves_the_furniture_with_the_map_it_labels():
    # Alignment moves the whole plot, so the axis labels keep their distance
    # from the data whichever edge of the cell the map sits on.
    def gaps(align):
        doc = i.document(width=180)
        doc.add('a', _map(height=50, aspect='equal'), align=align)
        compiled = doc.compile()
        area, ink = _areas(compiled)['a'], _ink(compiled)['a']
        return area.x0 - ink.x0, ink.x1 - area.x1, area.y0 - ink.y0, ink.y1 - area.y1

    centred, east = gaps('center'), gaps('e')
    assert east == pytest.approx(centred, abs=0.01)
    assert centred[0] > 0 and centred[2] > 0


# -- grow ---------------------------------------------------------------------

def _stacked(grow, height=170):
    doc = i.document(width=120, height=height)
    doc.add('map', _map(width=60, height=30, aspect='equal'), grow=grow)
    doc.add('bar', i.plot_spec(60, 30, x=(0, 20), y=(0, 10)).axes(), row=1)
    return doc.compile()


def test_grow_false_keeps_the_aspect_plot_at_its_natural_height():
    kept = _stacked(False)
    area = _areas(kept)['map']
    assert area.height == pytest.approx(30, abs=1e-6)
    assert area.width == pytest.approx(60, abs=1e-6)
    assert kept.metadata['cells']['map']['height'] < 45
    assert kept.metadata['layout']['rows'][1]['height'] > 100  # the other row takes it


def test_grow_true_gives_the_surplus_to_the_aspect_row_and_keeps_its_shape():
    grown = _stacked(True)
    area = _areas(grown)['map']
    assert grown.metadata['cells']['map']['height'] > 70
    assert area.width / area.height == pytest.approx(2.0, abs=1e-6)
    assert area.height < grown.metadata['cells']['map']['height'] - 20  # blank space above and below


def test_grow_false_alone_still_fills_a_fixed_page():
    # Documented: when no other cell can take the surplus, it is shared out
    # anyway, so the page height is filled. The shape still holds.
    doc = i.document(width=120, height=120)
    doc.add('a', _map(width=60, height=30, aspect='equal'), grow=False)
    compiled = doc.compile()
    assert compiled.metadata['height_mm'] == pytest.approx(120)
    area = _areas(compiled)['a']
    assert area.width / area.height == pytest.approx(2.0, abs=1e-6)


# -- layout report -------------------------------------------------------------

def test_layout_report_counts_an_aspect_plots_slack_as_unused():
    doc = i.document(width=180)
    doc.add('a', _map(height=50, aspect='equal'))
    report = doc.compile().metadata['layout']['cells']['a']
    assert report['unused_width'] > 50 and report['unused_height'] == pytest.approx(0, abs=0.01)
    plain = i.document(width=180)
    plain.add('a', _map(height=50))
    assert plain.compile().metadata['layout']['cells']['a']['unused_width'] == 0


# -- errors --------------------------------------------------------------------

def test_equal_needs_linear_numeric_scales():
    doc = i.document(width=120)
    doc.add('a', i.plot_spec(40, 30, x=log((1, 100)), y=(0, 10), aspect='equal'))
    with pytest.raises(ValueError, match="needs linear numeric x scales"):
        doc.compile()
    doc = i.document(width=120)
    doc.add('a', i.plot_spec(40, 30, x=['a', 'b'], y=(0, 10), aspect='equal'))
    with pytest.raises(ValueError, match="needs linear numeric x scales"):
        doc.compile()


def test_equal_needs_a_nonzero_span():
    doc = i.document(width=120)
    doc.add('a', i.plot_spec(40, 30, x=(5, 5), y=(0, 10), aspect='equal'))
    with pytest.raises(ValueError, match='nonzero x span'):
        doc.compile()


# -- one-call API --------------------------------------------------------------

def test_chart_aspect_reaches_the_plot_and_fits_its_domains():
    chart = i.chart(aspect='equal', xlim=(0, 20), ylim=(0, 10))
    chart.line(x=[0, 20], y=[0, 10])
    area = _areas(chart.document().compile())['chart']
    assert area.width / area.height == pytest.approx(2.0, abs=1e-6)


def test_chart_default_height_follows_its_width():
    # Without height=, an aspect chart is as tall as its shape asks, not the
    # default share of the page: a 0.3 chart is short and wide.
    chart = i.chart(aspect=0.3)
    chart.line(x=[0, 10], y=[0, 10])
    area = _areas(chart.document().compile())['chart']
    assert area.height / area.width == pytest.approx(0.3, abs=1e-6)


def test_chart_height_caps_an_aspect_chart():
    chart = i.chart(aspect='equal', height=20, xlim=(0, 10), ylim=(0, 10))
    chart.line(x=[0, 10], y=[0, 10])
    area = _areas(chart.document().compile())['chart']
    assert area.height == pytest.approx(20, abs=1e-6)
    assert area.width == pytest.approx(20, abs=1e-6)


def test_one_call_functions_take_aspect_and_reject_bad_values():
    data = {'x': [0.0, 20.0], 'y': [0.0, 10.0]}
    chart = i.scatter(data=data, x='x', y='y', aspect='equal', xlim=(0, 20), ylim=(0, 10))
    assert chart.spec.options['aspect'] == 'equal'
    with pytest.raises(ValueError, match='aspect must be'):
        i.scatter(data=data, x='x', y='y', aspect='square')


def test_chart_aspect_is_absent_by_default():
    assert 'aspect' not in i.chart().spec.options


# -- furniture that feeds back into the fit -------------------------------------

@pytest.mark.parametrize('shared', [False, True, 'all'])
def test_an_aspect_plot_beside_a_plain_one_settles_with_shared_furniture(shared):
    # The region's size depends on its furniture and the furniture on the
    # region; sharing margins must not stop the layout from settling.
    doc = i.document(width=160, columns=2, share_plot_margins=shared)
    doc.add('map', _map(height=40, aspect='equal').axes(y='A long response label / units'))
    doc.add('plain', i.plot_spec(height=40, x=(0, 20), y=(0, 10)).line([(0, 0), (20, 10)]).axes(),
            column=1)
    compiled = doc.compile()
    area = _areas(compiled)['map']
    assert area.width / area.height == pytest.approx(2.0, abs=1e-6)
    assert not any(d.code == 'OFF_CANVAS' for d in compiled.diagnostics)


def test_a_long_label_in_a_narrow_aspect_cell_keeps_the_scale():
    doc = i.document(width=90)
    doc.add('map', _map(height=40, aspect='equal')
            .axes(x='A very long horizontal label that wraps the furniture', y='Long vertical label'))
    compiled = doc.compile()
    area = _areas(compiled)['map']
    assert area.width / area.height == pytest.approx(2.0, abs=1e-6)


# -- nested grids and packed documents -------------------------------------------

def _regions(compiled):
    """Every plot region in page millimetres, found by walking the resolved tree."""
    placements = resolve(compiled.root)
    regions = {}
    for node in compiled.root.walk():
        area = plot_area(node)
        if area is not None and area.width > 5:
            regions[node.id] = area.transform(placements[node.id].world @ node.transform.inverse())
    return list(regions.values())


def test_an_aspect_plot_in_a_subfigure_keeps_its_scale():
    sub = i.subfigure(width=120)
    sub.add('m', _map(height=40, aspect='equal'))
    sub.add('n', _map(height=30))
    doc = i.document(width=160)
    doc.add('sub', sub)
    ratios = sorted(round(area.width / area.height, 6) for area in _regions(doc.compile()))
    assert 2.0 in ratios


def test_an_aspect_plot_in_a_packed_document_keeps_its_scale():
    doc = i.document(width=160, pack=True)
    doc.add('m', _map(height=40, aspect='equal'))
    doc.add('n', _map(height=30))
    ratios = {round(area.width / area.height, 6) for area in _regions(doc.compile())}
    assert 2.0 in ratios
