"""TEX_MATH: LaTeX typed into a label, which inklet prints literally. And a
layout drops or trims a chart title that repeats the panel letter it draws."""
import warnings

import pytest

import inklet as i


def _line(**kwargs):
    return i.line({'x': [1, 2, 3], 'y': [1, 4, 9]}, x='x', y='y', **kwargs)


def _tex(chart):
    return [d for d in chart.compile().lint() if d.code == 'TEX_MATH']


@pytest.mark.parametrize('label, rewrite', [
    ('$R^2$', 'R^{2}'),
    ('$\\alpha$ (s$^{-1}$)', 'α (s^{-1})'),
    ('Rate (s$^{-1}$)', 'Rate (s^{-1})'),
    ('$\\mu$m', 'µm'),
    ('$x^{2}$', 'x^{2}'),
    ('$\\mathrm{CO_2}$ rate', 'CO_{2} rate'),
])
def test_tex_math_fires_on_an_axis_label_and_suggests_the_rewrite(label, rewrite):
    chart = _line()
    chart.labels(y=label)
    diags = _tex(chart)
    assert len(diags) == 1
    assert diags[0].severity == 'warning'
    assert f"'{rewrite}'" in diags[0].hint
    assert 'printed literally' in diags[0].message


def test_tex_math_fires_on_a_chart_title():
    chart = _line()
    chart.labels(title='$R^2$')
    diags = _tex(chart)
    assert len(diags) == 1 and "'R^{2}'" in diags[0].hint


def test_greek_suggestion_is_unicode():
    chart = _line()
    chart.labels(y='$\\alpha$')
    assert 'α' in _tex(chart)[0].hint


@pytest.mark.parametrize('label', ['$5', 'Cost ($)', 'US$ millions', '$5–$10', 'US$', 'Prices in $USD and $EUR'])
def test_tex_math_is_silent_on_currency(label):
    chart = _line()
    chart.labels(y=label)
    assert not _tex(chart)


def test_a_layout_drops_a_title_that_is_only_the_panel_letter():
    plain = (_line() | _line()).compile().to_svg(text='names')
    with pytest.warns(UserWarning, match="chart title 'a' repeats the panel letter the layout adds; dropped it"):
        svg = (_line(title='a') | _line()).compile().to_svg(text='names')
    assert svg.count('>a<') == plain.count('>a<')


def test_a_layout_strips_the_panel_letter_from_the_front_of_a_title():
    a = _line(title='(a) Growth')
    with pytest.warns(UserWarning, match="repeats the panel letter the layout adds; kept 'Growth'"):
        svg = (a | _line()).compile().to_svg(text='names')
    assert 'Growth' in svg and '(a)' not in svg
    assert a.title == '(a) Growth'


@pytest.mark.parametrize('title, kept', [('a. Growth', 'Growth'), ('A: Growth', 'Growth'), ('a Growth', 'Growth')])
def test_other_panel_letter_forms_are_stripped(title, kept):
    with pytest.warns(UserWarning, match=f'kept {kept!r}'):
        svg = (_line(title=title) | _line()).compile().to_svg(text='names')
    assert kept in svg


def test_a_capital_article_at_the_front_of_a_title_is_kept():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        svg = (_line(title='A comparison') | _line()).compile().to_svg(text='names')
    assert not [w for w in caught if 'panel letter' in str(w.message)]
    assert 'comparison' in svg


def test_letters_false_keeps_the_title():
    chart = _line(title='a')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        svg = i.Layout('row', [chart, _line()], letters=False).compile().to_svg(text='names')
    assert not [w for w in caught if 'panel letter' in str(w.message)]
    assert '>a<' in svg
