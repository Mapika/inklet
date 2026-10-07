"""One-call charts: a Preset as the style, the main type size, slide figures, and widths in layouts."""
import warnings

import pytest

import inklet as i
from inklet.core import pt


DATA = {
    'time': [0, 1, 2, 3] * 2,
    'signal': [1.0, 3.0, 2.0, 4.0, 2.0, 4.0, 3.0, 5.0],
    'cond': ['ctrl'] * 4 + ['drug'] * 4,
}
MESSAGE = 'page width comes from Layout(width=...)'


def _line(**options):
    return i.line(DATA, x='time', y='signal', color='cond', **options)


def _bar(**options):
    return i.bar(DATA, x='cond', y='signal', **options)


def _layout_warnings(make):
    """The layout warnings raised while `make()` runs, and its result."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        result = make()
    return [w for w in caught if issubclass(w.category, UserWarning) and MESSAGE in str(w.message)], result


# -- a Preset as the style ----------------------------------------------------


def test_a_preset_object_is_accepted_and_its_font_size_is_used(tmp_path):
    style = i.preset('scientific.modern').customize(font_pt=12)
    chart = _line(style=style)
    assert chart.document().theme.font_size == pytest.approx(pt(12))
    chart.save(tmp_path / 'preset.svg')


def test_a_preset_keeps_its_own_page_unless_a_width_is_given():
    slide = i.preset('marketing.presentation')
    assert _line(style=slide).document().width == pytest.approx(254)
    assert _line(style=slide, width='double').document().width == pytest.approx(183)
    assert _line(style=slide, width=120).document().width == pytest.approx(120)


def test_a_preset_object_is_used_for_facets_too():
    figure = i.line(DATA, x='time', y='signal', facet_col='cond',
                    style=i.preset('scientific.nature')).compile()
    assert figure.root.bbox.width == pytest.approx(183, abs=0.5)


def test_an_unknown_style_name_raises_when_the_chart_is_made():
    with pytest.raises(ValueError) as caught:
        _line(style='scientific.modren')
    for name in i.preset_names():
        assert name in str(caught.value)


def test_a_style_that_is_neither_a_name_nor_a_preset_is_a_type_error():
    with pytest.raises(TypeError, match='preset name or a Preset'):
        _line(style=3)


# -- font_pt ----------------------------------------------------------------


def test_font_pt_sets_the_main_label_and_title_sizes():
    default = _line().document().theme
    theme = _line(font_pt=18).document().theme
    assert theme.font_size == pytest.approx(pt(18))
    assert theme.font_size_small == pytest.approx(pt(15.5))
    assert theme.font_size_large == pytest.approx(pt(18 * 9 / 7))
    assert theme.font_size > default.font_size


def test_font_pt_seven_is_the_default_scale():
    default = _line().document().theme
    theme = _line(font_pt=7).document().theme
    assert theme.font_size == pytest.approx(default.font_size)
    assert theme.font_size_small == pytest.approx(default.font_size_small)
    assert theme.font_size_large == pytest.approx(default.font_size_large)


def test_font_pt_overrides_the_size_of_a_preset():
    chart = _line(style=i.preset('marketing.presentation'), font_pt=14)
    assert chart.document().theme.font_size == pytest.approx(pt(14))


@pytest.mark.parametrize('bad', [0, -3, True, 'big'])
def test_font_pt_must_be_a_positive_size(bad):
    with pytest.raises(ValueError, match='font_pt'):
        _line(font_pt=bad)


def test_font_pt_is_a_chart_option_and_documented():
    from inklet import quick
    assert 'font_pt' in quick._CHART_OPTIONS
    assert 'font_pt' in i.line.__doc__


# -- slide figures ----------------------------------------------------------


def test_a_slide_figure_has_large_text_by_default():
    theme = _line(width='slide').document().theme
    assert theme.font_size >= pt(14)
    assert theme.font_size == pytest.approx(pt(14))


def test_a_slide_figure_with_the_presentation_style_has_larger_text():
    theme = _line(width='slide', style='marketing.presentation').document().theme
    assert theme.font_size == pytest.approx(pt(20))


# -- widths in a layout -----------------------------------------------------


def test_charts_with_widths_set_the_page_and_the_column_weights():
    layout = _line(width=60) | _bar(width=120)
    warned, doc = _layout_warnings(layout.document)
    assert not warned
    assert doc.width == pytest.approx(60 + 120 + doc.gap)
    assert doc.columns == pytest.approx((60, 120))
    assert layout.compile().root.bbox.width == pytest.approx(60 + 120 + doc.gap)


def test_the_column_weights_follow_the_chart_widths():
    _, doc = _layout_warnings((_line(width=60) | _bar(width=120)).document)
    narrow, wide = doc.columns
    assert wide == pytest.approx(2 * narrow)


def test_an_explicit_layout_width_wins_but_keeps_the_weights():
    layout = i.Layout('row', [_line(width=60), _bar(width=120)], width=200)
    warned, doc = _layout_warnings(layout.document)
    assert not warned
    assert doc.width == pytest.approx(200)
    assert doc.columns == pytest.approx((60, 120))


def test_a_layout_of_charts_without_widths_is_a_double_column():
    warned, doc = _layout_warnings((_line() | _bar()).document)
    assert not warned
    assert doc.width == pytest.approx(183)


def test_charts_that_all_set_one_named_width_do_not_warn():
    warned, doc = _layout_warnings((_line(width='double') | _bar(width='double')).document)
    assert not warned
    assert doc.width == pytest.approx(183)


def test_a_preset_style_on_a_row_keeps_the_presets_page():
    slide = i.preset('marketing.presentation')
    warned, doc = _layout_warnings((_line(style=slide) | _bar(style=slide)).document)
    assert not warned
    assert doc.width == pytest.approx(254)


def test_a_width_the_layout_ignores_warns_once():
    layout = i.Layout('row', [_line(width='single'), _bar(width=120), _bar(width='slide')])
    warned, _ = _layout_warnings(layout.document)
    assert len(warned) == 1
    assert issubclass(warned[0].category, UserWarning)


def test_a_stacked_chart_with_another_width_warns():
    warned, _ = _layout_warnings((_line(width=60) / _bar(width=120)).document)
    assert len(warned) == 1


def test_facets_with_a_width_do_not_warn():
    warned, _ = _layout_warnings(lambda: i.line(DATA, x='time', y='signal', facet_col='cond',
                                                width=120).document())
    assert not warned
