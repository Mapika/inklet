"""Call-time validation: help() shows the real signatures, and a bad option fails where it is written."""
import inspect
import pydoc

import pytest

import inklet as i
from inklet.plot import panel
from inklet.plot.panel import Panel

GROUPS = {'x': [0, 1, 2, 3], 'y': [1.0, 2.0, 3.0, 2.5], 'g': ['a', 'b', 'a', 'b']}
VOLCANO = {'lfc': [-2.0, -0.5, 0.2, 1.8, 2.5], 'p': [0.001, 0.4, 0.6, 0.01, 0.0005]}
FOREST = {'study': ['a', 'b', 'c'], 'or': [0.8, 1.2, 1.5], 'lo': [0.5, 0.9, 0.7], 'hi': [1.2, 1.6, 2.6]}
GRID = [[1.0, 2.0], [3.0, 4.0]]


# -- help() and inspect.signature() of recorded calls ----------------------

def test_chart_proxy_shows_the_panel_method_signature_and_doc():
    chart = i.line(x=[0, 1], y=[1, 2])
    parameters = list(inspect.signature(chart.vline).parameters)
    assert parameters[:5] == ['x', 'span', 'front', 'label', 'label_side']
    assert 'self' not in parameters
    assert chart.vline.__name__ == 'vline'
    text = pydoc.render_doc(chart.vline, renderer=pydoc.plaintext)
    assert 'vline(x, *, span' in text
    assert 'vertical rule' in text


def test_plot_spec_proxy_has_the_panel_parameters_plus_key():
    expected = [name for name in inspect.signature(Panel.vline).parameters if name != 'self']
    expected.insert(expected.index('style'), 'key')
    proxy = inspect.signature(i.plot_spec().vline)
    assert list(proxy.parameters) == expected
    assert proxy.parameters['key'].kind is inspect.Parameter.KEYWORD_ONLY
    assert proxy.parameters['key'].default is None


def test_plot_spec_proxy_documents_the_panel_method():
    recipe = i.plot_spec().vline
    assert recipe.__name__ == 'vline'
    assert 'vertical rule' in pydoc.render_doc(recipe, renderer=pydoc.plaintext)


_FORBIDDEN = {'build', 'twin_x', 'twin_y', 'point', 'coord', 'invert'}


def test_every_public_panel_method_has_a_proxy_with_key():
    recipe = i.plot_spec()
    names = [name for name, _ in inspect.getmembers(Panel, inspect.isfunction)
             if not name.startswith('_') and name not in _FORBIDDEN]
    for name in names:
        parameters = inspect.signature(getattr(recipe, name)).parameters
        assert 'self' not in parameters, name
        assert 'key' in parameters, name


# -- options with a fixed set of values --------------------------------------

def test_text_anchor_is_checked_when_the_call_is_recorded():
    with pytest.raises(ValueError, match=r"text\(\) anchor= must be one of 'c', 'center'.*'sw', "
                                         r"not 'west'"):
        i.plot_spec().text(1, 1, 'note', anchor='west')


@pytest.mark.parametrize('anchor', ['c', 'center', 'n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'])
def test_every_compass_point_is_a_text_anchor(anchor):
    i.plot_spec().text(1, 1, 'note', anchor=anchor)


def test_chart_text_anchor_fails_at_the_call():
    chart = i.line(x=[0, 1], y=[1, 2])
    with pytest.raises(ValueError, match="anchor= must be one of"):
        chart.text(1, 1, 'note', anchor='west')


def test_rule_label_side_is_checked_for_each_rule():
    with pytest.raises(ValueError, match=r"hline\(\) label_side= must be one of 'n', 's', not 'upside'"):
        i.plot_spec().hline(1, label='x', label_side='upside')
    with pytest.raises(ValueError, match=r"vline\(\) label_side= must be one of 'e', 'w', not 'n'"):
        i.plot_spec().vline(1, label='x', label_side='n')
    i.plot_spec().hline(1, label='x', label_side='s')
    i.plot_spec().vline(1, label='x', label_side='w')


def test_panel_methods_check_the_same_options_when_called():
    p = panel(40, 30, x=(0, 10), y=(0, 10))
    with pytest.raises(ValueError, match="label_side="):
        p.hline(1, label='x', label_side='upside')
    with pytest.raises(ValueError, match="anchor="):
        p.text(1, 1, 'note', anchor='west')


def test_legend_corner_and_side_are_checked():
    with pytest.raises(ValueError, match=r"legend\(\) corner= must be one of 'auto', 'best', "
                                         r"'nw', 'ne', 'sw', 'se', not 'middle'"):
        i.plot_spec().legend(corner='middle')
    with pytest.raises(ValueError, match=r"legend\(\) side= must be one of 'top', 'bottom', "
                                         r"'left', 'right', not 'middle'"):
        i.plot_spec().legend(side='middle')
    i.plot_spec().legend(corner=None, side='bottom')
    i.plot_spec().legend(corner='auto')


def test_chart_legend_option_is_checked_at_construction():
    with pytest.raises(ValueError, match="legend must be False"):
        i.chart(legend='middle')
    for value in (False, None, 'auto', 'direct', 'top', 'se'):
        i.chart(legend=value)


# -- save() and the to_* writers ---------------------------------------------

def test_save_refuses_an_unknown_keyword_before_writing(tmp_path):
    chart = i.line(x=[0, 1], y=[1, 2])
    with pytest.raises(TypeError, match=r"save\(\) got an unexpected keyword 'foo'; it accepts "
                                        r".*dpi=.*text="):
        chart.save(tmp_path / 'x.svg', foo=3)
    assert not (tmp_path / 'x.svg').exists()


def test_save_names_the_format_a_keyword_does_not_suit(tmp_path):
    chart = i.line(x=[0, 1], y=[1, 2])
    with pytest.raises(TypeError, match=r"compact=, which \.pdf output does not take"):
        chart.save(tmp_path / 'x.svg', tmp_path / 'x.pdf', compact=True)
    assert not (tmp_path / 'x.svg').exists()


def test_to_svg_checks_its_keywords_too():
    chart = i.line(x=[0, 1], y=[1, 2])
    with pytest.raises(TypeError, match=r"to_svg\(\) got an unexpected keyword 'foo'"):
        chart.to_svg(foo=1)


def test_save_accepts_dpi_for_vector_and_raster_alike(tmp_path):
    chart = i.line(x=[0, 1], y=[1, 2])
    chart.save(tmp_path / 'a.svg', tmp_path / 'a.pdf', dpi=300)
    assert (tmp_path / 'a.svg').exists() and (tmp_path / 'a.pdf').exists()


# -- one-call data and options ------------------------------------------------

def test_hist_of_a_bare_list_suggests_the_named_form():
    with pytest.raises(TypeError) as error:
        i.hist([1, 2, 3])
    assert 'i.hist(x=[1, 2, 3])' in str(error.value)
    i.hist(x=[1, 2, 3, 4]).compile()


@pytest.mark.parametrize('name', ['line', 'scatter', 'bar', 'boxplot', 'kde', 'survival'])
def test_one_call_functions_refuse_a_bare_list_as_data(name):
    with pytest.raises(TypeError, match=rf"i\.{name}\(\) needs data= to be a table"):
        getattr(i, name)([1, 2, 3])


def test_chart_methods_refuse_a_bare_list_as_data():
    with pytest.raises(TypeError, match="sequence of values, not a table"):
        i.chart().hist([1, 2, 3])


def test_heatmap_refuses_a_flat_list_of_values():
    with pytest.raises(TypeError, match="rows of values"):
        i.heatmap([1, 2, 3])


def test_heatmap_colorbar_title_names_the_colour_bar():
    assert i.heatmap(GRID, colorbar_title='r').to_svg() == i.heatmap(GRID, colorbar='r').to_svg()


def test_heatmap_colorbar_and_colorbar_title_conflict():
    with pytest.raises(ValueError, match="colorbar= or colorbar_title="):
        i.heatmap(GRID, colorbar=False, colorbar_title='r')


@pytest.mark.parametrize('make', [
    lambda **k: i.line(GROUPS, x='x', y='y', **k),
    lambda **k: i.scatter(GROUPS, x='x', y='y', **k),
    lambda **k: i.bar(GROUPS, x='g', y='y', **k),
    lambda **k: i.hist(GROUPS, x='y', **k),
    lambda **k: i.kde(GROUPS, x='y', **k),
    lambda **k: i.boxplot(GROUPS, x='g', y='y', **k),
    lambda **k: i.violin(GROUPS, x='g', y='y', **k),
    lambda **k: i.strip(GROUPS, x='g', y='y', **k),
    lambda **k: i.area(GROUPS, x='x', y='y', **k),
    lambda **k: i.heatmap(GRID, **k),
    lambda **k: i.survival(GROUPS, time='y', event='x', **k),
    lambda **k: i.volcano(VOLCANO, x='lfc', y='p', **k),
    lambda **k: i.quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi', **k),
])
def test_unknown_keyword_fails_at_the_call_and_lists_the_options(make):
    with pytest.raises(TypeError, match=r"got unknown option foo=; it accepts .*, and paint "
                                        r"keywords such as stroke="):
        make(foo=3)


def test_unknown_keyword_suggests_the_close_name():
    with pytest.raises(TypeError, match=r"colorbar_titel= \(did you mean colorbar_title=\?\)"):
        i.heatmap(GRID, colorbar_titel='r')


def test_foreign_paint_spelling_is_suggested():
    with pytest.raises(TypeError, match=r"colour= \(did you mean color=\?\)"):
        i.bar(GROUPS, x='g', y='y', colour='red')


def test_mark_specific_options_still_reach_their_marks():
    i.volcano(VOLCANO, x='lfc', y='p', top=2).compile()
    i.quick.forest(FOREST, label='study', estimate='or', lower='lo', upper='hi',
                   summary_line=True).compile()
