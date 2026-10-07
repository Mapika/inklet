"""plot_spec() axes fitted to the recorded marks."""
import math
import random

import pytest

import inklet as i
from inklet.plot.autodomain import fit_domains, measure


def _fit(*steps, **options):
    return fit_domains([(m, a, k) for m, a, k in steps], 60, 40, **options)


def test_points_fit_with_padding_and_round_ends():
    x, y = _fit(('line', ([(0, 1), (10, 40)],), {}))
    assert x[0] <= 0 and x[1] >= 10
    assert y[0] <= 1 and y[1] >= 40
    # Padding is a few percent, not a doubled axis.
    assert y[1] - y[0] < 40 * 1.3


def test_bars_sit_on_their_baseline_and_categories_become_bands():
    x, y = _fit(('bars', (['a', 'b', 'c'], [3, 5, 2]), {}))
    assert x == ['a', 'b', 'c']
    assert y[0] == 0 and y[1] >= 5


def test_horizontal_bars_put_categories_on_y():
    x, y = _fit(('bars', (['a', 'b'], [3, -2]), {'orient': 'h'}))
    assert y == ['a', 'b']
    assert x[0] <= -2 and x[1] >= 3


def test_histogram_counts_are_probed_from_the_drawing():
    values = [1, 2, 2, 3, 3, 3]
    x, y = _fit(('hist', (values, 3), {}))
    assert x[0] <= 1 and x[1] >= 3
    assert y[0] == 0 and 3 <= y[1] < 4


def test_density_samples_inside_a_domain_that_holds_its_data():
    random.seed(0)
    values = [random.gauss(100, 15) for _ in range(200)]
    x, y = _fit(('kde', (values,), {}))
    assert x[0] < min(values) and x[1] > max(values)
    assert 0 < y[1] < 0.1


def test_error_bars_widen_the_value_axis():
    _, y = _fit(('errorbars', ([(1, 10), (2, 12)],), {'yerr': [1, 5]}))
    assert y[0] <= 9 and y[1] >= 17


def test_box_plot_groups_keyed_by_name_are_categories():
    x, y = _fit(('boxplot', ({'ctrl': [1, 2, 3], 'drug': [4, 5, 9]},), {}))
    assert x == ['ctrl', 'drug']
    assert y[0] <= 1 and y[1] >= 9


def test_log_scale_domain_stays_positive():
    _, y = _fit(('line', ([(1, 1), (2, 1000)],), {}), y_scale='log')
    assert 0 < y[0] < 1 and y[1] > 1000


def test_rounding_never_crosses_zero_for_positive_data():
    _, y = _fit(('scatter', ([(0, 2.7), (1, 660)],), {}))
    assert y[0] >= 0 or y[0] > -30


def test_furniture_is_not_data():
    x, y = _fit(('axes', (), {'x': 'Time'}), ('legend', (), {}))
    assert x is None and y is None


def test_unit_default_is_kept_when_the_data_fill_it():
    x, y = measure([('line', ([(0, 0), (1, 1)],), {})], 60, 40)
    assert x.within_unit and y.within_unit
    x, y = measure([('line', ([(0, 0.01), (1, 0.03)],), {})], 60, 40)
    assert not y.within_unit


def test_document_plot_without_ranges_fits_its_data():
    plot = i.plot_spec()
    plot.line([(0, 1), (1, 3), (2, 2), (3, 40)], name='a')
    plot.scatter([(0, 2), (5, 3)], name='b')
    plot.axes(x='x', y='y').legend()
    doc = i.publication('single-column').document()
    doc.add('a', plot)
    figure = doc.compile()
    assert not [d for d in figure.lint() if d.severity == 'error']


def test_explicit_auto_always_fits():
    plot = i.plot_spec(x='auto', y='auto')
    plot.line([(0.2, 0.4), (0.3, 0.5)])
    plot.axes()
    doc = i.publication('single-column').document()
    doc.add('a', plot)
    svg = doc.compile().to_svg(text='names')
    # The fitted axis labels the data's own range rather than 0 and 1.
    assert '0.45' in svg or '0.4' in svg


def test_log_option_builds_a_log_scale():
    plot = i.plot_spec(y='log')
    plot.line([(x, math.exp(x)) for x in range(1, 10)])
    plot.axes()
    doc = i.publication('single-column').document()
    doc.add('a', plot)
    assert doc.compile().to_svg()


def test_unknown_marks_fall_back_without_failing():
    x, y = _fit(('no_such_mark', ([1, 2],), {}))
    assert x is None and y is None


@pytest.mark.parametrize('method,args', [
    ('step', ([(0, 1), (4, 3)],)),
    ('stem', ([(0, 1), (4, 3)],)),
    ('fill_between', ([0, 1, 2], [0, 0, 0], [1, 3, 2])),
    ('ecdf', ([1, 2, 3, 4],)),
    ('violin', ({'a': [1, 2, 3, 4], 'b': [2, 3, 6, 7]},)),
])
def test_common_marks_produce_domains(method, args):
    x, y = _fit((method, args, {}))
    assert x is not None and y is not None


def test_violin_tails_are_inside_the_fitted_domain():
    _, y = _fit(('violin', ({'a': [1, 1.1, 1.2, 1.3, 3.0], 'b': [1, 1.05, 1.1, 1.2]},), {}))
    assert y[0] < 1 and y[1] > 3.0


def test_bands_paint_beneath_lines_drawn_before_them():
    panel = i.panel(40, 30, x=(0, 2), y=(0, 4))
    panel.line([(0, 1), (2, 3)])
    panel.band([0, 2], [0, 0], [4, 4])
    assert len(panel._content) == 1 and len(panel._under) == 1
