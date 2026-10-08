"""Quick API and plot_spec calls are refused where they are written, not at save.

A keyword the drawing code would reject, an option value outside its choices,
a label list that cannot pair with its points, and a colour bar with no ramp
all used to fail when the chart compiled, far from the line that wrote them.
Each test here makes the bad call alone and checks it raises at the call.
"""

import pytest

import inklet as i
from inklet.core import DiagramError


DATA = {
    't': [0, 1, 2, 3],
    'v': [1.0, 3.0, 2.0, 4.0],
    'cond': ['a', 'a', 'b', 'b'],
}


def _line():
    return i.line(DATA, x='t', y='v')


# -- option names, checked where the call is written ------------------------

@pytest.mark.parametrize('call, message', [
    (lambda: _line().line(DATA, x='t', y='v', method='cubic'), r"line\(\) got unknown keyword method="),
    (lambda: _line().scatter(DATA, x='t', y='v', markersize=4), r"scatter\(\) got unknown keyword markersize= \(did you mean size=\?\)"),
    (lambda: _line().annotate(1, 2, 'peak', label_side='upside'), r"annotate\(\) got unknown keyword label_side="),
    (lambda: _line().legend(cornr='top'), r"legend\(\) got unknown keyword cornr= \(did you mean corner=\?\)"),
    (lambda: i.heatmap(DATA, x='t', y='cond', z='v').colorbar(sidee='right'),
     r"colorbar\(\) got unknown keyword sidee= \(did you mean side=\?\)"),
    (lambda: _line().axes(bogus=1), r"axes\(\) got unknown keyword bogus="),
    (lambda: _line().label_points([(1, 2), (2, 3)], ['a', 'b'], sizze=3),
     r"label_points\(\) got unknown keyword sizze= \(did you mean size=\?\)"),
    (lambda: i.plot_spec().line([(0, 0), (1, 1)], bogus=1), r"line\(\) got unknown keyword bogus="),
    (lambda: i.plot_spec().annotate(1, 2, 'x', label_side='up'), r"annotate\(\) got unknown keyword label_side="),
    (lambda: i.plot_spec().twin_y(sizze=3), r"twin_y\(\) got unknown keyword sizze="),
    (lambda: i.plot_spec().twin_x(sizze=3), r"twin_x\(\) got unknown keyword sizze="),
])
def test_an_unknown_keyword_is_refused_at_the_call(call, message):
    with pytest.raises(TypeError, match=message):
        call()


@pytest.mark.parametrize('call, message', [
    (lambda: i.heatmap(DATA, x='t', y='cond', z='v').colorbar(side='upside'),
     r"colorbar\(\) side= must be one of"),
    (lambda: _line().annotate(1, 2, 'peak', side='upside'), r"annotate\(\) side= must be one of"),
    (lambda: _line().legend(side='upside'), r"legend\(\) side= must be one of"),
])
def test_an_option_value_outside_its_choices_is_refused_at_the_call(call, message):
    with pytest.raises(ValueError, match=message):
        call()


def test_keywords_the_chain_really_takes_still_work():
    # Names the method passes on to its drawing code, and paint, are not refused.
    chart = _line()
    chart.annotate(1, 2, 'peak', size=3, leader=False, fill='#333333')
    assert chart.compile() is not None


def test_a_colour_bar_keyword_the_chain_takes_is_accepted():
    chart = i.heatmap([[1, 2], [3, 4]], x=['a', 'b'], y=['r1', 'r2'])
    chart.colorbar(title='z', tick_font_size=6, ticks=[1, 2, 3], format='{:.1f}')
    assert chart.compile() is not None


# -- label_points: blank labels and mismatched lengths ----------------------

def test_a_blank_label_is_refused_at_the_call_with_its_index():
    with pytest.raises(ValueError, match=r"label_points\(\) needs text: labels\[1\] is empty"):
        _line().label_points([(1, 2), (2, 3)], ['a', '   '])


def test_a_blank_label_is_refused_on_a_bare_plot_spec_too():
    with pytest.raises(ValueError, match=r"labels\[0\] is empty"):
        i.plot_spec().label_points([(1, 2)], [''])


def test_a_label_list_of_the_wrong_length_is_refused_at_the_call():
    with pytest.raises(DiagramError, match=r"got 1 labels for 2 points"):
        _line().label_points([(1, 2), (2, 3)], ['a'])


def test_a_label_list_passed_by_keyword_is_checked_too():
    with pytest.raises(ValueError, match=r"labels\[1\] is empty"):
        _line().label_points(points=[(1, 2), (2, 3)], labels=['a', ''])


def test_labels_with_words_are_accepted():
    chart = _line().label_points([(1, 2), (2, 3)], ['a', 'b'], fill='#222222')
    assert 'label_points' in repr(chart)


# -- title, xlabel, ylabel and grid: read as values, callable to set -------

def test_calling_title_sets_it_and_returns_the_chart():
    chart = _line()
    assert chart.title('Growth') is chart
    assert chart.title == 'Growth'
    assert chart.title + '!' == 'Growth!'
    assert chart.title.upper() == 'GROWTH'


def test_the_label_and_grid_setters_return_the_chart():
    chart = _line()
    assert chart.xlabel('Time') is chart
    assert chart.ylabel('Signal') is chart
    assert chart.grid(True) is chart
    assert (chart.xlabel, chart.ylabel) == ('Time', 'Signal')
    assert chart.grid == True and bool(chart.grid)


def test_an_unset_title_and_grid_read_as_none_and_false():
    chart = _line()
    assert chart.title == None and not chart.title
    assert chart.grid == None and not chart.grid


def test_assignment_still_sets_the_value():
    chart = _line()
    chart.title = 'Assigned'
    chart.grid = 'y'
    assert chart.title == 'Assigned' and chart.grid == 'y'
    assert chart._title == 'Assigned' and chart._grid == 'y'


def test_the_set_title_is_the_one_drawn():
    chart = _line().title('Growth')
    assert 'Growth' in chart.to_svg()


def test_a_grid_set_by_call_is_drawn():
    plain = _line().to_svg()
    gridded = _line().grid('both').to_svg()
    assert gridded != plain


def test_a_label_set_by_call_reaches_the_axis():
    chart = _line().xlabel('Elapsed time').ylabel('Response')
    svg = chart.to_svg()
    assert 'Elapsed time' in svg and 'Response' in svg


def test_a_facet_layout_reads_the_grid_its_charts_agreed_on():
    # Layout._agreed reads each chart's grid; the wrapper must not defeat it.
    layout = i.line(DATA, x='t', y='v', facet_col='cond', grid='y')
    charts = list(layout.charts())
    assert len(charts) == 2 and all(chart.grid == 'y' for chart in charts)


# -- colorbar needs a colour scale -------------------------------------------

def test_colorbar_on_a_chart_with_no_ramp_is_refused_at_the_call():
    with pytest.raises(ValueError, match=r"colorbar\(\) needs a colour scale: draw a heatmap, "
                                         r"or a scatter with color= a numeric column"):
        _line().colorbar()


def test_colorbar_on_a_heatmap_is_accepted():
    _ = i.heatmap(DATA, x='t', y='cond', z='v').colorbar(title='z')


def test_colorbar_on_a_scatter_coloured_by_a_number_is_accepted():
    # A colour column is a ramp only when it has more distinct numbers than groups allowed.
    table = {'x': list(range(20)), 'y': [v * v for v in range(20)], 'z': [v / 3 for v in range(20)]}
    _ = i.scatter(table, x='x', y='y', color='z').colorbar(title='z')


def test_colorbar_with_its_own_source_is_accepted_without_a_ramp():
    _ = _line().colorbar(source='viridis')


# -- PlotSpec.twin_x: a working recipe, not an empty one --------------------

def _twinned_svg(with_child):
    doc = i.publication('single-column').document()
    spec = i.plot_spec(x=(0, 4), y=(0, 5))
    spec.line([(0, 1), (1, 2), (2, 3)])
    if with_child:
        spec.twin_x().line([(0, 100), (4, 900)])
    doc.add('plot', spec)
    return doc.compile().to_svg()


def test_plot_spec_twin_x_with_marks_draws_the_second_axis():
    # The child's own scale appears only when its marks are drawn.
    plain, twinned = _twinned_svg(False), _twinned_svg(True)
    assert '900' in twinned and '900' not in plain
