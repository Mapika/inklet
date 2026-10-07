"""Thousands separators on linear tick labels, and the quick API's xformat= and yformat=."""
import re

import pytest

import inklet as i
from inklet import quick
from inklet.plot.axis import tick_texts
from inklet.plot.scale import broken, format_number, linear

MINUS = "−"

DATA = {
    'x': [1, 2, 3, 4, 5, 6],
    'y': [2.0, 3.0, 1.0, 4.0, 2.5, 3.5],
    'g': ['b', 'a', 'b', 'c', 'a', 'c'],
}

FOREST = {
    'study': ['A', 'B', 'C'],
    'or': [1.2, 0.8, 1.5],
    'lo': [0.9, 0.5, 1.1],
    'hi': [1.6, 1.3, 2.0],
}


def _axes_options(chart):
    (axes,) = [step for step in chart.plot()._steps if step[1] == 'axes']
    return axes[3]


def _texts(chart):
    """The text nodes of the rendered SVG, which is what a reader sees."""
    return set(re.findall(r">([^<]+)<", chart.to_svg(text='names')))


# -- grouping -------------------------------------------------------------------


@pytest.mark.parametrize("value, label", [
    (5000, "5000"),          # four figures stay bare
    (10000, "10,000"),       # five figures take the comma
    (25000, "25,000"),
    (99999, "99,999"),
    (100000, "1e5"),         # past five figures the exponent form is unchanged
    (-25000, MINUS + "25,000"),
])
def test_five_figures_group_and_four_do_not(value, label):
    assert linear((-100000, 100000)).tick_labels([value]) == (label,)


def test_a_shared_step_groups_every_label_on_the_axis():
    labels = linear((0, 30000)).tick_labels([10000, 10500, 11000])
    assert labels == ("10,000", "10,500", "11,000")


def test_decimals_are_grouped_in_the_integer_part_only():
    assert linear((10000, 10001)).tick_labels([10000, 10000.5]) == ("10,000.0", "10,000.5")


def test_negative_grouped_values_keep_the_typographic_minus():
    labels = linear((-30000, 30000)).tick_labels([-30000, -10000, 0, 5000, 10000])
    assert labels == (MINUS + "30,000", MINUS + "10,000", "0", "5000", "10,000")
    assert all("-" not in label for label in labels)


def test_a_broken_axis_groups_like_a_linear_one():
    scale = broken((0.0, 30000.0), breaks=[(5000.0, 20000.0)])
    assert scale.tick_labels([0, 25000]) == ("0", "25,000")


def test_format_number_itself_is_not_grouped():
    # Bar values, wheel labels and the rest call format_number directly; only
    # the axis tick labels take the separator.
    assert format_number(25000) == "25000"


def test_si_and_explicit_formats_are_not_grouped_by_the_axis():
    scale = linear((0, 60000))
    si = tick_texts(scale, (25000, 50000), si=True)
    assert all("," not in text for text in si)
    assert tick_texts(scale, (25000,), format='{:.0f}') == ("25000",)


def test_a_chart_renders_grouped_tick_labels():
    chart = i.scatter({'x': [0, 1], 'y': [-30000, 30000]}, x='x', y='y')
    texts = _texts(chart)
    assert "30,000" in texts and MINUS + "30,000" in texts
    assert "30000" not in texts and "-30000" not in texts


# -- xformat= and yformat= ------------------------------------------------------


def test_yformat_and_xformat_reach_the_axes_options():
    chart = i.scatter(DATA, x='x', y='y', yformat='{:.0%}', xformat='{:,.0f}')
    kwargs = _axes_options(chart)
    assert kwargs['y_options'] == {'format': '{:.0%}'}
    assert kwargs['x_options'] == {'format': '{:,.0f}'}


def test_a_callable_format_is_passed_through_unchanged():
    def money(value):
        return f"${value:,.2f}"

    kwargs = _axes_options(i.scatter(DATA, x='x', y='y', yformat=money))
    assert kwargs['y_options']['format'] is money


def test_no_format_option_leaves_the_axes_options_alone():
    kwargs = _axes_options(i.scatter(DATA, x='x', y='y'))
    assert 'format' not in kwargs.get('y_options', {})
    assert 'format' not in kwargs.get('x_options', {})


def test_the_chart_constructor_takes_the_formats():
    chart = i.Chart(xformat='{:,.0f}', yformat='%')
    assert (chart.xformat, chart.yformat) == ('{:,.0f}', '%')


def test_a_percent_spec_renders_as_percent():
    chart = i.scatter({'x': [0, 1], 'y': [0.0, 0.6]}, x='x', y='y', yformat='{:.0%}')
    texts = _texts(chart)
    assert {"0%", "20%", "40%", "60%"} <= texts


def test_a_suffix_is_appended_to_the_scale_labels():
    chart = i.scatter({'x': [0, 1], 'y': [0, 50]}, x='x', y='y', yformat='%')
    texts = _texts(chart)
    assert "50%" in texts and "0%" in texts
    assert "50" not in texts


def test_a_string_spec_wins_over_the_default_grouping():
    chart = i.scatter({'x': [0, 1], 'y': [0, 30000]}, x='x', y='y', yformat='{:.0f} m')
    texts = _texts(chart)
    assert "30000 m" in texts
    assert "30,000" not in texts


def test_xformat_renders_on_the_x_axis():
    chart = i.scatter({'x': [0, 30000], 'y': [0, 1]}, x='x', y='y', xformat='{:,.0f} m')
    assert "30,000 m" in _texts(chart)


def test_a_callable_format_renders_its_own_text():
    chart = i.scatter(DATA, x='x', y='y', yformat=lambda v: f"<{v:g}>")
    # Markup in the callable's text is escaped, so the brackets arrive as entities.
    assert re.search(r"&lt;\d[^&]*&gt;", chart.to_svg(text='names'))


def test_formats_reach_every_facet():
    layout = i.scatter(DATA, x='x', y='y', yformat='%', facet_col='g')
    charts = list(layout.charts())
    assert len(charts) == 3
    for chart in charts:
        assert _axes_options(chart)['y_options']['format'] == '%'


def test_a_forest_refuses_the_formats_it_cannot_apply():
    with pytest.raises(ValueError, match="forest does not take xformat= or yformat="):
        quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi', xformat='{:.1f}')


@pytest.mark.parametrize("option", ["xformat", "yformat"])
def test_a_format_must_be_a_string_or_a_callable(option):
    with pytest.raises(TypeError, match=option):
        i.Chart(**{option: 2})
