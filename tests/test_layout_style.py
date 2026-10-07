"""Figure options on a layout: explicit options, agreement between charts, palettes per panel."""
import warnings

import pytest

import inklet as i


def _chart(*names, **options):
    """A line chart with one three-point series per name, in the order given."""
    rows = {'x': [0, 1, 2] * len(names), 'y': [1.0, 2.0, 3.0] * len(names),
            'group': [name for name in names for _ in range(3)]}
    return i.line(rows, x='x', y='y', color='group', **options)


def _panels(figure):
    """Per panel, the colour each named series is drawn in."""
    return [{step[3]['name']: step[3]['color'] for step in cell.item._steps if step[1] == 'line'}
            for cell in figure.document()._cells]


def _disagreements(make):
    """The result of `make()`, and the warnings it raised about charts that disagree."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = make()
    return result, [str(w.message) for w in caught
                    if issubclass(w.category, UserWarning) and 'disagree' in str(w.message)]


# -- explicit layout options --------------------------------------------------


def test_layout_options_set_the_style_font_and_grid_of_the_figure():
    layout = i.Layout('row', [_chart('a'), _chart('b')], style='scientific.nature', font_pt=8, grid=True)
    doc = layout.document()
    assert doc.preset.name == 'scientific.nature'
    assert doc.preset.publication.font_pt == 8
    assert doc.preset.plot.grid == 'both'


def test_an_explicit_option_wins_over_charts_that_disagree_and_does_not_warn():
    layout = _chart('a', style='scientific.nature', font_pt=9) | _chart('b', style='scientific.modern', font_pt=7)
    layout.options(style='scientific.modern', font_pt=8)
    doc, notes = _disagreements(layout.document)
    assert notes == []
    assert doc.preset.name == 'scientific.modern'
    assert doc.preset.publication.font_pt == 8


def test_options_returns_the_layout_and_sets_them_after_the_fact():
    layout = _chart('a') | _chart('b')
    assert layout.options(style='scientific.nature', font_pt=8) is layout
    doc = layout.document()
    assert doc.preset.name == 'scientific.nature'
    assert doc.preset.publication.font_pt == 8


def test_options_none_clears_an_option_so_the_charts_decide_again():
    layout = (_chart('a', font_pt=9) | _chart('b', font_pt=9)).options(font_pt=8)
    assert layout.document().preset.publication.font_pt == 8
    assert layout.options(font_pt=None).document().preset.publication.font_pt == 9


def test_the_constructor_takes_palette_font_and_grid():
    layout = i.Layout('column', [_chart('a'), _chart('b')], palette='okabe-ito', font_pt=8, grid=False)
    assert (layout.palette, layout.font_pt, layout.grid) == ('okabe-ito', 8, False)
    assert layout.document().preset.publication.font_pt == 8


def test_an_option_set_on_a_layout_inside_another_applies_to_the_figure():
    inner = (_chart('a') | _chart('b')).options(font_pt=8)
    figure = inner / _chart('c')
    assert figure.document().preset.publication.font_pt == 8


def test_options_reject_unknown_names_and_bad_values():
    layout = _chart('a') | _chart('b')
    with pytest.raises(TypeError, match='layout options are'):
        layout.options(colour='red')
    with pytest.raises(ValueError, match='unknown style'):
        layout.options(style='no-such-style')
    with pytest.raises(ValueError, match='font_pt'):
        layout.options(font_pt=0)


# -- what the charts agree on -------------------------------------------------


def test_charts_that_agree_decide_the_figure_without_a_warning():
    layout = _chart('a', style='scientific.nature', font_pt=8, grid=True) | \
        _chart('b', style='scientific.nature', font_pt=8, grid=True)
    doc, notes = _disagreements(layout.document)
    assert notes == []
    assert doc.preset.name == 'scientific.nature'
    assert doc.preset.publication.font_pt == 8
    assert doc.preset.plot.grid == 'both'


def test_charts_that_disagree_warn_once_per_setting_and_the_first_chart_wins():
    layout = _chart('a', style='scientific.nature', font_pt=9, grid=True) | \
        _chart('b', style='scientific.modern', font_pt=7, grid=False)
    doc, notes = _disagreements(layout.document)
    assert len(notes) == 3
    (style,) = [n for n in notes if 'on style ' in n]
    (font,) = [n for n in notes if 'on font_pt ' in n]
    (grid,) = [n for n in notes if 'on grid ' in n]
    assert "('scientific.nature', 'scientific.modern')" in style
    assert "style='scientific.nature'" in style
    assert '(9, 7)' in font and 'font_pt=9' in font
    assert '(True, False)' in grid and 'grid=True' in grid
    assert doc.preset.name == 'scientific.nature'
    assert doc.preset.publication.font_pt == 9
    assert doc.preset.plot.grid == 'both'


def test_a_chart_without_a_font_size_disagrees_with_one_that_sets_it():
    layout = _chart('a', font_pt=8) | _chart('b')
    doc, notes = _disagreements(layout.document)
    assert len(notes) == 1 and 'font_pt' in notes[0]
    assert doc.preset.publication.font_pt == 8


def test_palettes_that_differ_do_not_warn():
    layout = _chart('a', palette='tol-bright') | _chart('b', palette='okabe-ito')
    _, notes = _disagreements(layout.document)
    assert notes == []


# -- palettes are per panel ---------------------------------------------------


def test_each_panel_keeps_its_own_palette():
    alone_a = _panels(_chart('control', palette='tol-bright'))[0]
    alone_b = _panels(_chart('control', palette='okabe-ito'))[0]
    panels = _panels(_chart('control', palette='tol-bright') | _chart('control', palette='okabe-ito'))
    assert panels == [alone_a, alone_b]
    assert panels[0]['control'] != panels[1]['control']


def test_a_palette_set_on_the_layout_colours_every_panel():
    layout = (_chart('control', palette='tol-bright') | _chart('control', palette='okabe-ito')).options(palette='okabe-ito')
    panels = _panels(layout)
    assert panels[0] == panels[1] == _panels(_chart('control', palette='okabe-ito'))[0]


def test_a_chart_without_a_palette_takes_the_figures_palette():
    panels = _panels(_chart('control', palette='okabe-ito') | _chart('control'))
    assert panels[0] == panels[1]


# -- one series name, one colour ----------------------------------------------


@pytest.mark.parametrize('palette', [None, 'okabe-ito'])
def test_a_series_name_keeps_its_colour_across_panels_whatever_the_order(palette):
    options = {} if palette is None else {'palette': palette}
    layout = _chart('treatment', 'control', **options) | _chart('control', **options)
    left, right = _panels(layout)
    assert left['control'] == right['control']
    assert left['treatment'] != left['control']


def test_a_series_name_keeps_its_colour_in_a_grid_and_in_nested_layouts():
    first = _chart('treatment', 'control', palette='okabe-ito')
    second = _chart('control', palette='okabe-ito')
    third = _chart('placebo', 'control', palette='okabe-ito')
    grid = i.Layout('grid', [first, second, third], columns=3)
    colours = [panel['control'] for panel in _panels(grid)]
    assert colours[0] == colours[1] == colours[2]
    nested = (_chart('control', palette='okabe-ito') | _chart('placebo', 'control', palette='okabe-ito')) / \
        _chart('treatment', 'control', palette='okabe-ito')
    assert len({panel['control'] for panel in _panels(nested)}) == 1


def test_a_single_chart_colours_its_series_as_before():
    panels = _panels(_chart('treatment', 'control', palette='okabe-ito'))
    assert list(panels[0].values()) == ['#000000', '#e69f00']
