"""Preset option `axes='box'`: a closed black frame with inward ticks.

These checks are about measured geometry and resolved style on the compiled
page, not about pixels. Frame edges come from the spines, a tick is inside the
frame when its box is, and the stroke and ink are the ones the renderer
inherits.
"""

from __future__ import annotations

import math

import pytest

import inklet as i
from inklet.core import Style, resolve
from inklet.plot.axis import SPINE_KIND, TICK_KIND, TICK_LABEL_KIND

EPS = 1e-6
BLACK = '#000000'


def _line_spec(**axes):
    xs = [k * 0.1 for k in range(31)]
    spec = i.plot_spec(x=(0, 3), y=(0, 2))
    spec.line([(x, 1 + 0.9 * math.sin(x)) for x in xs], name='Response')
    spec.axes(x='Time / s', y='Signal / a.u.', **axes).legend()
    return spec


def _compiled(axes=None, spec=None, **preset):
    options = {} if axes is None else {'axes': axes}
    doc = i.preset('scientific.nature', format='single-column', **options, **preset).document()
    doc.add('figure', spec if spec is not None else _line_spec())
    return doc.compile()


def _placed(compiled, kind):
    return [p for p in resolve(compiled.root).values() if p.diagram.kind == kind]


def _frame(compiled):
    """The rectangle the spines enclose, from the horizontal and vertical runs."""
    spines = [p.bbox for p in _placed(compiled, SPINE_KIND)]
    horizontal = [b for b in spines if abs(b.height) < EPS and b.width > EPS]
    vertical = [b for b in spines if abs(b.width) < EPS and b.height > EPS]
    return dict(horizontal=horizontal, vertical=vertical)


def _sides(compiled):
    """Spines and ticks grouped by the side they stand on."""
    runs = _frame(compiled)
    ticks = [p.bbox for p in _placed(compiled, TICK_KIND)]
    return runs, [b for b in ticks if abs(b.width) < EPS], [b for b in ticks if abs(b.height) < EPS]


def _effective(root):
    """(node, style) for every node, with the style each one inherits from its ancestors."""
    found = []

    def visit(node, inherited):
        style = node.style.over(inherited)
        found.append((node, style))
        for child in node.children:
            visit(child, style)

    visit(root, Style())
    return found


def _mm_tick_length(box):
    return max(abs(box.width), abs(box.height))


# -- the option itself ---------------------------------------------------------


def test_axes_option_is_stored_on_the_preset_and_defaults_to_open():
    assert i.preset('scientific.nature').plot.axes == 'open'
    assert i.preset('scientific.nature', axes='box').plot.axes == 'box'
    assert i.preset('scientific.nature', axes='box').customize(axes='open').plot.axes == 'open'


def test_axes_option_rejects_unknown_values():
    with pytest.raises(ValueError, match='axes must be open or box'):
        i.preset('scientific.nature', axes='frame')


@pytest.mark.parametrize('name', ['scientific.nature', 'educational.textbook', 'marketing.report'])
def test_axes_option_is_available_on_every_family(name):
    assert i.preset(name, axes='box').plot.axes == 'box'


# -- the frame --------------------------------------------------------------------


def test_box_draws_four_spines_that_enclose_the_plot():
    runs = _frame(_compiled('box'))
    assert len(runs['horizontal']) >= 2, 'a top and a bottom spine'
    assert len(runs['vertical']) >= 2, 'a left and a right spine'
    tops = sorted({round(b.y0, 6) for b in runs['horizontal']})
    lefts = sorted({round(b.x0, 6) for b in runs['vertical']})
    assert len(tops) == 2 and len(lefts) == 2, 'two distinct edges per direction'


def test_open_draws_only_the_bottom_and_left_spines():
    runs = _frame(_compiled('open'))
    assert len(runs['horizontal']) == 1
    assert len(runs['vertical']) == 1


def test_default_is_open():
    assert _frame(_compiled()) == _frame(_compiled('open'))


# -- ticks ------------------------------------------------------------------------


def test_box_ticks_point_inward_on_all_four_sides():
    compiled = _compiled('box')
    runs, vertical_ticks, horizontal_ticks = _sides(compiled)
    top = min(b.y0 for b in runs['horizontal'])
    bottom = max(b.y1 for b in runs['horizontal'])
    left = min(b.x0 for b in runs['vertical'])
    right = max(b.x1 for b in runs['vertical'])
    for box in vertical_ticks + horizontal_ticks:
        assert box.x0 >= left - EPS and box.x1 <= right + EPS, f'tick {box} leaves the frame sideways'
        assert box.y0 >= top - EPS and box.y1 <= bottom + EPS, f'tick {box} leaves the frame'
    # Ticks stand on each edge, not only on one of them.
    assert any(abs(b.y1 - bottom) < EPS or abs(b.y0 - bottom) < EPS for b in vertical_ticks)
    assert any(abs(b.y0 - top) < EPS or abs(b.y1 - top) < EPS for b in vertical_ticks)
    assert any(abs(b.x0 - left) < EPS or abs(b.x1 - left) < EPS for b in horizontal_ticks)
    assert any(abs(b.x0 - right) < EPS or abs(b.x1 - right) < EPS for b in horizontal_ticks)


def test_box_major_ticks_are_one_to_one_and_a_half_millimetres():
    _runs, vertical_ticks, horizontal_ticks = _sides(_compiled('box'))
    lengths = [_mm_tick_length(b) for b in vertical_ticks + horizontal_ticks]
    major = max(lengths)
    assert 1.0 - EPS <= major <= 1.5 + EPS, f'major tick is {major:.3f} mm'


def test_box_has_minor_ticks_on_every_side():
    _runs, vertical_ticks, horizontal_ticks = _sides(_compiled('box'))
    for group in (vertical_ticks, horizontal_ticks):
        lengths = [_mm_tick_length(b) for b in group]
        major = max(lengths)
        minor = [n for n in lengths if n < 0.8 * major]
        assert minor, 'minor ticks are present on this pair of sides'
        # The axis's own subdivision length, a little over half the major tick.
        assert all(abs(n / major - 0.55) < 0.02 for n in minor), 'minor ticks are about 55-60% of the major length'


def test_open_has_no_minor_ticks():
    _runs, vertical_ticks, horizontal_ticks = _sides(_compiled('open'))
    for group in (vertical_ticks, horizontal_ticks):
        lengths = {round(_mm_tick_length(b), 6) for b in group}
        assert len(lengths) == 1, lengths


def test_per_call_minor_false_wins_over_the_preset():
    compiled = _compiled('box', spec=_line_spec(minor=False))
    _runs, vertical_ticks, horizontal_ticks = _sides(compiled)
    for group in (vertical_ticks, horizontal_ticks):
        assert len({round(_mm_tick_length(b), 6) for b in group}) == 1


def test_x_options_tick_size_wins_on_the_bottom_axis():
    # The bottom ticks are the vertical tick boxes that touch the bottom spine.
    compiled = _compiled('box', spec=_line_spec(x_options=dict(tick_size=1)))
    runs, vertical_ticks, _horizontal = _sides(compiled)
    bottom = max(b.y1 for b in runs['horizontal'])
    bottom_ticks = [b for b in vertical_ticks
                    if abs(b.y0 - bottom) < EPS or abs(b.y1 - bottom) < EPS]
    assert bottom_ticks
    lengths = sorted({round(_mm_tick_length(b), 2) for b in bottom_ticks})
    assert lengths == [0.55, 1.0], 'the explicit 1 mm major tick wins, and its minor ticks follow it'
    # The left axis keeps the preset's inward major length.
    left_ticks = [b for b in _horizontal if abs(b.x0 - min(r.x0 for r in runs['vertical'])) < EPS
                  or abs(b.x1 - min(r.x0 for r in runs['vertical'])) < EPS]
    assert left_ticks and max(_mm_tick_length(b) for b in left_ticks) > 1.0


# -- ink and stroke ------------------------------------------------------------------


def test_box_frame_and_ticks_are_black_at_least_point_six():
    compiled = _compiled('box')
    lines = [(node, style) for node, style in _effective(compiled.root)
             if node.kind in (SPINE_KIND, TICK_KIND)]
    assert lines
    for node, style in lines:
        assert style.stroke == BLACK, f'{node.kind} stroke is {style.stroke}'
        assert style.stroke_width >= 0.21 - EPS, f'{node.kind} width is {style.stroke_width} mm'


def test_box_labels_are_black():
    compiled = _compiled('box')
    labels = [style for node, style in _effective(compiled.root) if node.kind == TICK_LABEL_KIND]
    assert labels
    assert all(style.text_fill == BLACK for style in labels)


def test_open_keeps_the_default_ink_and_stroke():
    compiled = _compiled('open')
    spines = [style for node, style in _effective(compiled.root) if node.kind == SPINE_KIND]
    assert spines and all(style.stroke == '#1a1a1a' for style in spines)
    assert all(abs(style.stroke_width - 0.108) < EPS for style in spines)


def test_open_is_the_default_and_writes_the_same_bytes(tmp_path):
    outputs = []
    for options in ({}, {'axes': 'open'}):
        doc = i.preset('scientific.nature', format='single-column', **options).document()
        doc.add('figure', _line_spec())
        path = tmp_path / f"open{len(outputs)}.svg"
        doc.save(str(path))
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1]


# -- headings, facets and heatmaps -------------------------------------------------


def test_heatmap_gets_the_frame_without_ticks_over_the_cells():
    spec = i.plot_spec(x=(-0.5, 3.5), y=(-0.5, 2.5))
    spec.matrix([[r * 4 + c for c in range(4)] for r in range(3)],
                x=list(range(4)), y=list(range(3)))
    spec.axes(x='Column', y='Row')
    compiled = _compiled('box', spec=spec)
    runs = _frame(compiled)
    assert len(runs['horizontal']) >= 2 and len(runs['vertical']) >= 2
    top = min(b.y0 for b in runs['horizontal'])
    right = max(b.x1 for b in runs['vertical'])
    _runs, vertical_ticks, horizontal_ticks = _sides(compiled)
    on_top = [b for b in vertical_ticks if abs(b.y0 - top) < EPS or abs(b.y1 - top) < EPS]
    on_right = [b for b in horizontal_ticks if abs(b.x0 - right) < EPS or abs(b.x1 - right) < EPS]
    assert not on_top and not on_right


def test_quick_chart_styled_with_the_box_preset_gets_the_frame():
    style = i.preset('scientific.nature', format='single-column', axes='box')
    data = {'step': [0, 1, 2, 3], 'value': [1.0, 2.0, 1.5, 2.5]}
    chart = i.line(data, x='step', y='value', style=style)
    runs = _frame(chart.document().compile())
    assert len(runs['horizontal']) >= 2 and len(runs['vertical']) >= 2


# -- lint -------------------------------------------------------------------------


def test_lint_is_clean_on_a_framed_line_plot():
    compiled = _compiled('box')
    codes = {d.code for d in compiled.lint() if d.code != 'FONT_SUBSTITUTED'}
    assert codes == set(), compiled.report()


def test_lint_is_clean_when_the_data_touches_the_frame():
    # The first point sits on the bottom edge, the last on the right, and the
    # peak on the top, so the data meets every side of the frame.
    xs = [k * 0.1 for k in range(31)]
    ys = [1 + 0.9 * math.sin(x) for x in xs]
    ys[0], ys[-1] = 0.0, 2.0
    spec = i.plot_spec(x=(0, 3), y=(0, 2))
    spec.line(list(zip(xs, ys)), name='Response')
    spec.axes(x='Time / s', y='Signal / a.u.').legend()
    compiled = _compiled('box', spec=spec)
    codes = {d.code for d in compiled.lint() if d.code != 'FONT_SUBSTITUTED'}
    assert codes == set(), compiled.report()


# -- log axes and data weight ------------------------------------------------------


def _minor_and_major(node):
    """Tick lengths on one axis, split into majors and minors by their length."""
    from inklet.draw.coords import as_drawn
    boxes = [p.bbox for p in resolve(as_drawn(node)).values()
             if p.diagram.kind == TICK_KIND]
    lengths = [_mm_tick_length(b) for b in boxes]
    major = max(lengths)
    return ([n for n in lengths if n >= 0.8 * major], [n for n in lengths if n < 0.8 * major])


def test_log_axis_has_two_to_nine_in_each_decade_under_box_style():
    from inklet.document.spec import _box_style
    from inklet.plot import axis, log
    from inklet.themes import theme as get_theme
    kwargs = {'ticks': (1.0, 10.0, 100.0)}
    _box_style(kwargs, get_theme('nature'))
    majors, minors = _minor_and_major(axis(log((1, 100), (0, 50)), **kwargs))
    assert len(majors) == 3
    assert len(minors) == 16, 'the eight mantissas 2 to 9 in each of the two decades'


def test_log_minor_ticks_survive_when_the_sparse_mantissas_are_all_majors():
    # On 2.8 to 130 the 2-and-5 set is entirely labelled majors (5, 20, 50), and
    # used to end the search, so a y axis like this drew no minor ticks at all.
    from inklet.plot import axis, log
    majors, minors = _minor_and_major(axis(log((2.8, 130.0), (0, 40)),
                                           ticks=(5.0, 10.0, 20.0, 50.0, 100.0), minor=True))
    assert len(majors) == 5
    assert len(minors) >= 8


def test_box_log_axes_have_minor_ticks_on_all_four_sides():
    compiled = _compiled('box', spec=_log_spec())
    _runs, vertical_ticks, horizontal_ticks = _sides(compiled)
    for group in (vertical_ticks, horizontal_ticks):
        lengths = [_mm_tick_length(b) for b in group]
        major = max(lengths)
        assert any(n < 0.8 * major for n in lengths), 'minor ticks on this pair of sides'


def test_box_data_line_is_at_least_as_heavy_as_the_frame():
    compiled = _compiled('box')
    effective = _effective(compiled.root)
    frame_width = min(style.stroke_width for node, style in effective if node.kind == SPINE_KIND)
    data = [style for node, style in effective
            if node.kind not in (SPINE_KIND, TICK_KIND, TICK_LABEL_KIND)
            and style.stroke not in (None, 'none', BLACK, '#1a1a1a')
            and style.stroke_width is not None and style.stroke_width > 0.1]
    assert data
    assert all(style.stroke_width >= 0.25 - EPS for style in data)
    assert all(style.stroke_width >= frame_width - EPS for style in data)


def test_explicit_stroke_width_still_wins_under_box():
    spec = i.plot_spec(x=(0, 3), y=(0, 2))
    spec.line([(0, 0), (3, 2)], name='Thin', stroke_width=0.1)
    spec.axes(x='Time / s', y='Signal / a.u.')
    compiled = _compiled('box', spec=spec)
    widths = [style.stroke_width for node, style in _effective(compiled.root)
              if node.kind not in (SPINE_KIND, TICK_KIND, TICK_LABEL_KIND)
              and style.stroke not in (None, 'none', BLACK, '#1a1a1a')
              and style.stroke_width is not None and style.stroke_width > 0.05]
    assert widths and all(abs(w - 0.1) < EPS for w in widths)


def _log_spec():
    pts = [(10 ** (k / 10), 3 * (10 ** (k / 10)) ** 0.8) for k in range(21)]
    spec = i.plot_spec(x='log', y='log')
    spec.scatter(pts, name='Data')
    spec.axes(x='Frequency / Hz', y='Power / W')
    return spec
