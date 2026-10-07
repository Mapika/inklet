"""Quick API options: minor ticks, facet order, and readable size-key labels."""
from datetime import date

import pytest

import inklet as i


DATA = {
    'x': [1, 2, 3, 4, 5, 6],
    'y': [2.0, 3.0, 1.0, 4.0, 2.5, 3.5],
    'g': ['b', 'a', 'b', 'c', 'a', 'c'],
    'n': [10, 2, 10, 2, 5, 5],
}


def _axes_options(chart):
    (axes,) = [step for step in chart.plot()._steps if step[1] == 'axes']
    return axes[3]


def _titles(layout):
    return [chart.title for chart in layout.charts()]


# -- minor ticks --------------------------------------------------------------


def test_minor_ticks_reach_the_axes_options():
    chart = i.scatter(DATA, x='x', y='y', xminor=True, yminor=4)
    kwargs = _axes_options(chart)
    assert kwargs['x_options'] == {'minor': True}
    assert kwargs['y_options'] == {'minor': 4}


def test_minor_ticks_default_to_absent_and_one_axis_can_be_set_alone():
    assert 'x_options' not in _axes_options(i.scatter(DATA, x='x', y='y'))
    only_y = _axes_options(i.scatter(DATA, x='x', y='y', yminor=2))
    assert only_y['y_options'] == {'minor': 2}
    assert 'minor' not in only_y.get('x_options', {})


def test_minor_ticks_survive_a_facet_grid_and_render():
    grid = i.scatter(DATA, x='x', y='y', facet_col='g', xminor=2)
    for chart in grid.charts():
        # Inner panels also hide their tick numbers; the minor setting is separate.
        assert _axes_options(chart)['x_options']['minor'] == 2
    assert '<svg' in grid.to_svg()


def test_minor_ticks_are_a_chart_option_on_the_chart_class():
    chart = i.Chart(xminor=True)
    assert chart.xminor is True and chart.yminor is None


# -- facet order ----------------------------------------------------------------


def test_numeric_facets_default_to_ascending_order():
    assert _titles(i.scatter(DATA, x='x', y='y', facet_col='n')) == ['n = 2', 'n = 5', 'n = 10']


def test_date_facets_default_to_ascending_order():
    rows = [{'x': 1, 'y': 1, 'day': date(2024, 3, 2)},
            {'x': 2, 'y': 2, 'day': date(2024, 1, 9)},
            {'x': 3, 'y': 3, 'day': date(2024, 2, 1)}]
    titles = _titles(i.scatter(rows, x='x', y='y', facet_col='day'))
    assert titles == ['day = 2024-01-09', 'day = 2024-02-01', 'day = 2024-03-02']


def test_text_facets_keep_first_appearance_order():
    assert _titles(i.scatter(DATA, x='x', y='y', facet_col='g')) == ['b', 'a', 'c']


def test_explicit_facet_order_is_drawn_in_the_listed_order():
    grid = i.scatter(DATA, x='x', y='y', facet_col='g', facet_order=['c', 'b', 'a'])
    assert _titles(grid) == ['c', 'b', 'a']
    numbers = i.scatter(DATA, x='x', y='y', facet_col='n', facet_order=[5, 10, 2])
    assert _titles(numbers) == ['n = 5', 'n = 10', 'n = 2']


def test_facet_order_applies_to_rows_and_to_columns():
    rows = i.scatter(DATA, x='x', y='y', facet_row='g', facet_order=['c', 'a', 'b'])
    assert [t.split(' ')[0] for t in _titles(rows)] == ['c', 'a', 'b']
    both = i.scatter(DATA, x='x', y='y', facet_row='g', facet_col='n',
                     facet_order={'g': ['c', 'a', 'b'], 'n': [10, 5, 2]})
    cells = _titles(both)
    assert cells[0] == 'c · n = 10' and cells[1] == 'c · n = 5' and cells[-1] == 'b · n = 2'


def test_a_facet_order_that_leaves_out_a_value_raises():
    with pytest.raises(ValueError, match="'c'"):
        i.scatter(DATA, x='x', y='y', facet_col='g', facet_order=['a', 'b'])


def test_facet_order_needs_a_facet_and_known_names():
    with pytest.raises(ValueError, match='needs facet_col= or facet_row='):
        i.scatter(DATA, x='x', y='y', facet_order=['a'])
    with pytest.raises(ValueError, match="'other'"):
        i.scatter(DATA, x='x', y='y', facet_col='g', facet_order={'other': ['a']})


# -- size-key labels ------------------------------------------------------------


def _key_svg(values=None, **options):
    p = i.panel(70, 50, x=(0, 1), y=(0, 1))
    p.scatter([(0.3, 0.4), (0.7, 0.6)], size=2)
    p.size_key(i.plot.area_scale(1e7, 10), values=values, **options)
    return i.to_svg(p.build(), text='names')


def test_size_key_labels_read_as_words_for_millions():
    svg = _key_svg(values=[2.5e6, 1e7])
    assert '10 million' in svg and '2.5 million' in svg
    assert '1e7' not in svg and '10000000' not in svg


def test_size_key_labels_use_thousands_separators_below_a_million():
    svg = _key_svg(values=[50000, 250000])
    assert '50,000' in svg and '250,000' in svg


def test_size_key_labels_for_billions_and_small_values_are_unchanged():
    from inklet.plot.dotplot import _key_texts
    assert _key_texts([1.5e9, 2e9], ('a', 'b')) == ('1.5 billion', '2 billion')
    assert _key_texts([12, 500], ('12', '500')) == ('12', '500')


def test_an_explicit_format_still_wins_over_the_default_labels():
    svg = _key_svg(values=[1e7], format='{:.0f}')
    assert '10000000' in svg and '10 million' not in svg


def test_default_key_labels_for_a_scale_up_to_ten_million():
    svg = _key_svg()
    assert '10 million' in svg
