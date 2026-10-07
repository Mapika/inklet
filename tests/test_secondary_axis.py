"""A right-hand y axis for quick charts (`secondary_y=`), and `chart.twin_y` refused."""
import re

import pytest

import inklet as i


MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
DATA = {
    'month': MONTHS,
    'rain': [50, 40, 60, 70, 80, 90, 120, 110, 100, 80, 70, 60],
    'temp': [5, 6, 9, 13, 17, 21, 24, 23, 19, 13, 8, 5],
}
# Two colour groups: A sits in single digits, B near two hundred.
SCATTER = {
    'dose': [1, 2, 3, 4, 5, 6, 1, 2, 3, 4, 5, 6],
    'response': [2, 4, 5, 7, 8, 8.5, 60, 90, 130, 150, 170, 185],
    'drug': ['A'] * 6 + ['B'] * 6,
}


def _clean(chart):
    figure = chart.compile()
    serious = [d for d in figure.lint() if d.severity in ('error', 'warning')]
    assert not serious, figure.report()
    return figure


def _tick_groups(svg):
    """Numeric tick labels, one list per fill colour, lowest first.

    Each y axis draws its numbers in its own colour (ink on the left, the
    series colour on a right axis), so the groups are the axes. Month names
    on the x axis are not numbers and drop out.
    """
    groups = {}
    for fill, text in re.findall(r'<text[^>]*?fill="([^"]+)"[^>]*>([^<]+)</text>', svg):
        if re.fullmatch(r'-?\d+(\.\d+)?', text):
            groups.setdefault(fill, []).append(float(text))
    return sorted(groups.values(), key=max)


def _right_step(spec):
    """The keyed right-hand axis instruction of a plot recipe."""
    steps = [step for step in spec._steps if step[1] == 'twin_y']
    assert len(steps) == 1, spec
    return steps[0]


def _line_colours(recipe):
    """The colour each named line is drawn in, by name."""
    return {step[3]['name']: step[3]['color'] for step in recipe._steps
            if step[1] == 'line' and 'name' in step[3]}


def test_the_right_axis_is_titled_with_its_column_name():
    svg = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp').to_svg()
    # Each column is its axis title and its legend entry; the left title is 'rain'.
    assert svg.count('>temp<') == 2 and svg.count('>rain<') == 2


def test_the_right_axis_title_can_be_overridden():
    chart = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp')
    chart.labels(y='Rainfall / mm', y2='Mean temperature / °C')
    svg = chart.to_svg()
    assert 'Mean temperature / °C' in svg and 'Rainfall / mm' in svg


def test_the_left_axis_fits_only_its_own_series():
    svg = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp').to_svg()
    _, left = _tick_groups(svg)
    # Rain runs 40 to 120. Had temperature (5 to 24) reached the left axis, its
    # ticks would start at 0 or 20.
    assert min(left) >= 30 and 120 <= max(left) <= 160


def test_the_right_axis_fits_only_its_own_series():
    svg = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp').to_svg()
    right, _ = _tick_groups(svg)
    # Temperature runs 5 to 24. Rain's 120 must not stretch this axis.
    assert 24 <= max(right) <= 30 and min(right) <= 10


def test_the_legend_lists_both_series():
    chart = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp')
    chart.labels(y2='Mean temperature')
    svg = chart.to_svg()
    # With the right title overridden, 'temp' is in the picture only as the
    # legend's entry; 'rain' is the left title and the legend's entry.
    assert svg.count('>rain<') == 2 and svg.count('>temp<') == 1
    spec = chart.plot()
    assert set(_line_colours(spec)) == {'rain'}
    assert set(_line_colours(_right_step(spec)[2][0])) == {'temp'}


def test_one_series_on_the_right_takes_its_colour():
    chart = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp')
    spec = chart.plot()
    right = _right_step(spec)
    series = _line_colours(right[2][0])['temp']
    assert right[3]['color'] is not None
    assert right[3]['color'] == series
    assert f'stroke="{series}"' in chart.to_svg()


def test_two_series_on_the_right_leave_the_axis_plain():
    data = dict(DATA, humidity=[80, 78, 72, 66, 60, 58, 70, 74, 76, 79, 82, 84])
    chart = i.line(data, x='month', y=['rain', 'temp', 'humidity'],
                   secondary_y=['temp', 'humidity'])
    right = _right_step(chart.plot())
    assert right[3]['color'] is None
    assert right[3]['label'] == 'temp, humidity'
    _clean(chart)


def test_scatter_puts_a_colour_group_on_the_right():
    chart = i.scatter(SCATTER, x='dose', y='response', color='drug', secondary_y='B')
    _clean(chart)
    left, right = _tick_groups(chart.to_svg())
    assert max(left) <= 10
    assert min(right) >= 50 and max(right) >= 150


def test_a_name_that_draws_no_series_is_refused_before_drawing():
    chart = i.line(DATA, x='month', y=['rain', 'temp'])
    steps = len(chart.spec._steps)
    with pytest.raises(ValueError, match="'humidity'"):
        chart.line(DATA, x='month', y='temp', secondary_y='humidity')
    assert len(chart.spec._steps) == steps


def test_every_series_on_the_right_with_nothing_on_the_left_is_refused():
    with pytest.raises(ValueError, match='left axis'):
        i.line(DATA, x='month', y='temp', secondary_y='temp')


def test_bar_has_no_secondary_axis_and_says_so():
    with pytest.raises(TypeError, match='secondary_y'):
        i.bar(DATA, x='month', y='rain', secondary_y='rain')


def test_bars_with_a_line_on_the_right_axis():
    chart = i.bar(DATA, x='month', y='rain')
    chart.line(DATA, x='month', y='temp', secondary_y='temp')
    chart.labels(y='Rainfall / mm')
    _clean(chart)
    right, left = _tick_groups(chart.to_svg())
    assert max(left) >= 120 and max(right) <= 30


def test_facets_share_one_right_hand_scale():
    rows = {
        'month': MONTHS * 2,
        'site': ['north'] * 12 + ['south'] * 12,
        'rain': DATA['rain'] + [v * 2 for v in DATA['rain']],
        'temp': DATA['temp'] + [v + 4 for v in DATA['temp']],
    }
    layout = i.line(rows, x='month', y=['rain', 'temp'], secondary_y='temp', facet_col='site')
    scales = set()
    for chart in layout.charts():
        step = next(step for step in chart.spec._steps if step[0] == 'secondary_y')
        scales.add(step[3]['scale'])
    assert len(scales) == 1 and None not in scales
    _clean(layout)


def test_chart_twin_y_is_refused_and_points_at_secondary_y():
    chart = i.line(DATA, x='month', y='rain')
    with pytest.raises(TypeError, match='secondary_y'):
        chart.twin_y((0, 30), label='Temperature')


def test_chart_twin_x_is_refused_too():
    chart = i.line(DATA, x='month', y='rain')
    with pytest.raises(TypeError, match='twin_x'):
        chart.twin_x((0, 30))


def test_a_document_twin_axis_does_not_stretch_the_parent():
    # The document model directly: 0 to 6 on the left, 200 to 1000 on a
    # coloured right axis, sharing x. The left must stay near its own data.
    p = i.plot_spec().line([(0, 1), (4, 6)], name='left').axes()
    p.twin_y(label='right', color='#8a1f7a').line([(0, 200), (4, 1000)], name='right')
    d = i.document(width=110)
    d.add('main', p)
    left, right = _tick_groups(d.compile().to_svg())
    assert max(left) <= 8
    assert max(right) >= 1000


def test_a_document_twin_axis_stretches_the_shared_x_to_its_data():
    p = i.plot_spec().line([(0, 1), (4, 6)], name='left').axes()
    p.twin_y(label='right', color='#8a1f7a').line([(0, 200), (40, 1000)], name='right')
    d = i.document(width=110)
    d.add('main', p)
    left, _ = _tick_groups(d.compile().to_svg())
    # Left holds the x ticks as well as the y ticks; the twin's x of 40 must reach them.
    assert max(left) >= 40


def test_twin_marks_do_not_leak_palette_slots_into_the_drawing():
    # The twin's marks are recorded in their own recipe; a palette slot left
    # unresolved there would be drawn literally.
    svg = i.line(DATA, x='month', y=['rain', 'temp'], secondary_y='temp').to_svg()
    assert '@series' not in svg
