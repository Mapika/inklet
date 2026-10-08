"""Horizontal category charts read top-down, title their axes by physical side, and fit."""
import warnings

import pytest

import inklet as i
from inklet import quick
from inklet.core import Vec2


CATS = {'cat': ['A', 'B', 'C'], 'v': [3, 1, 2]}
REPEATED = {'cat': ['A', 'A', 'B', 'B', 'C', 'C'], 'v': [1, 2, 3, 4, 5, 6]}
STACKED = {'cat': ['A', 'B', 'C', 'A', 'B', 'C'], 'g': ['p', 'p', 'p', 'q', 'q', 'q'],
           'v': [3, 1, 2, 1, 2, 3]}
SPREAD = {'cat': ['A'] * 3 + ['B'] * 3 + ['C'] * 3, 'v': [1, 2, 3, 4, 5, 9, 2, 3, 4]}


def _texts(chart, kind):
    """The compiled position (x, y) of each text of one kind, by its string.

    Figure space runs down the page, so a smaller y is higher up.
    """
    found = {}
    for node in chart.compile().scene.walk():
        text = getattr(node.prim, 'text', None)
        if node.kind == kind and isinstance(text, str):
            point = node.world.apply(Vec2(0, 0))
            found.setdefault(text, (point.x, point.y))
    return found


def _rows_top_down(chart, names):
    ys = {name: y for name, (_, y) in _texts(chart, 'tick-label').items() if name in names}
    assert set(ys) == set(names), 'every category should have a tick label'
    return sorted(names, key=ys.__getitem__)


@pytest.mark.parametrize('make', [
    lambda: i.bar(CATS, x='cat', y='v', orient='h'),
    lambda: i.bar(REPEATED, x='cat', y='v', orient='h', agg='mean'),
    lambda: i.bar(REPEATED, x='cat', y='v', orient='h', agg='median', error_y='sem'),
    lambda: i.bar(STACKED, x='cat', y='v', color='g', orient='h', stacked=True),
    lambda: i.bar(STACKED, x='cat', y='v', color='g', orient='h'),
    lambda: i.lollipop(CATS, x='cat', y='v', orient='h'),
    lambda: i.boxplot(SPREAD, x='cat', y='v', orient='h'),
    lambda: i.boxplot(SPREAD, x='cat', y='v', orient='h', points=True),
    lambda: i.violin(SPREAD, x='cat', y='v', orient='h'),
    lambda: i.strip(SPREAD, x='cat', y='v', orient='h'),
], ids=['bar', 'bar-mean', 'bar-median-sem', 'bar-stacked', 'bar-grouped', 'lollipop',
        'boxplot', 'boxplot-points', 'violin', 'strip'])
def test_horizontal_category_charts_list_the_first_row_at_the_top(make):
    assert _rows_top_down(make(), ['A', 'B', 'C']) == ['A', 'B', 'C']


def test_vertical_bars_still_run_left_to_right():
    xs = {name: x for name, (x, _) in _texts(i.bar(CATS, x='cat', y='v'), 'tick-label').items()}
    assert xs['A'] < xs['B'] < xs['C']


def test_horizontal_bar_rows_follow_the_table_not_an_alphabetical_sort():
    shuffled = {'cat': ['C', 'A', 'B'], 'v': [1, 2, 3]}
    assert _rows_top_down(i.bar(shuffled, x='cat', y='v', orient='h'), ['C', 'A', 'B']) == ['C', 'A', 'B']


# -- axis titles -------------------------------------------------------------

def test_horizontal_bar_titles_the_value_axis_with_the_column_below_the_plot():
    titles = _texts(i.bar(CATS, x='cat', y='v', orient='h'), 'axis-label')
    assert titles['v'][1] > titles['cat'][1]    # the value title is under the plot
    assert titles['cat'][0] < titles['v'][0]    # the category title is left of it


def test_vertical_bar_titles_the_value_axis_on_the_left_for_contrast():
    titles = _texts(i.bar(CATS, x='cat', y='v'), 'axis-label')
    assert titles['v'][0] < titles['cat'][0]
    assert titles['cat'][1] > titles['v'][1]


@pytest.mark.parametrize('make', [
    lambda: i.bar(REPEATED, x='cat', y='v', orient='h', agg='mean'),
    lambda: i.lollipop(CATS, x='cat', y='v', orient='h'),
    lambda: i.boxplot(SPREAD, x='cat', y='v', orient='h'),
    lambda: i.violin(SPREAD, x='cat', y='v', orient='h'),
    lambda: i.strip(SPREAD, x='cat', y='v', orient='h'),
], ids=['bar-mean', 'lollipop', 'boxplot', 'violin', 'strip'])
def test_horizontal_value_title_is_the_value_column_on_the_value_axis(make):
    titles = _texts(make(), 'axis-label')
    assert titles['v'][1] > titles['cat'][1]
    assert titles['cat'][0] < titles['v'][0]


def test_labels_name_the_physical_axes_of_a_horizontal_bar():
    chart = i.bar(CATS, x='cat', y='v', orient='h').labels(x='Count', y='Pathway')
    titles = _texts(chart, 'axis-label')
    assert titles['Count'][1] > titles['Pathway'][1]
    assert titles['Pathway'][0] < titles['Count'][0]


# -- forest ------------------------------------------------------------------

FOREST = {'study': ['A', 'B', 'C'], 'est': [0.8, 1.1, 0.9], 'lo': [0.6, 0.9, 0.7],
          'hi': [1.0, 1.3, 1.1], 'participants': [120, 85, 240]}


def _forest(**options):
    return quick.forest(FOREST, label='study', estimate='est', lower='lo', upper='hi', **options)


def test_forest_with_two_right_columns_fits_a_single_column():
    # Hazard ratio's header is wider than Estimate's; it used to need 81.05 mm of 81.
    figure = _forest(right=['ci', 'participants'], measure='Hazard ratio').compile()
    assert figure.root.bbox.width == pytest.approx(89, abs=0.5)


def test_forest_narrows_its_plot_only_as_far_as_its_columns_need():
    chart = _forest(right=['ci', 'participants'], measure='Hazard ratio')
    rows, options = chart._forest
    theme = chart._profile().theme
    fitted = quick._fit_forest(rows, options, 81.0, theme)['width']
    assert quick._FOREST_MIN_PLOT <= fitted < 36.0
    assert quick._fit_forest(rows, options, 89.0, theme)['width'] == 36.0


def test_forest_with_too_many_columns_names_the_fix():
    with pytest.raises(i.LayoutError, match="fewer right= columns or width='double'"):
        _forest(right=['ci', 'participants', 'participants', 'participants', 'participants']).compile()


# -- layouts -----------------------------------------------------------------

def _large(figure):
    return [d.message for d in figure.lint() if d.code == 'LARGE_TEXT']


def test_nature_layout_letters_are_no_larger_than_its_titles_at_font_pt_9():
    # A one-letter title would be taken for the panel letter and dropped.
    scatter = dict(style='scientific.nature', font_pt=9, title='Trial')
    d = {'x': [1, 2, 3], 'y': [2, 1, 3]}
    single = _large(i.scatter(d, x='x', y='y', **scatter).compile())
    layout = _large((i.scatter(d, x='x', y='y', **scatter) | i.scatter(d, x='x', y='y', **scatter))
                    .options(style='scientific.nature', font_pt=9).compile())
    letters = [m for m in layout if m.startswith("the letter")]
    assert letters and all('renders at 9.0pt' in m for m in letters), letters
    others = [m for m in layout if not m.startswith("the letter")]
    assert len(others) == 2 * len(single)


def test_a_slide_chart_after_the_first_in_a_row_warns_about_the_page_width():
    d = {'x': [1, 2], 'y': [2, 1]}
    plain = i.scatter(d, x='x', y='y')
    slide = i.scatter(d, x='x', y='y', width='slide')
    with pytest.warns(UserWarning, match='set widths on the layout'):
        (plain | slide).compile()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        (slide | plain).compile()
    assert not [w for w in caught if 'set widths on the layout' in str(w.message)]
