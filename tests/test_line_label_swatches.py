"""Direct curve labels in ink, each after a short line in its curve's colour:
Nature asks for keys rather than coloured text."""
import pytest

import inklet as i
from inklet.core import resolve
from inklet.plot.line_labels import LINE_LABEL_KIND, LINE_SWATCH_KIND

COLOURS = {'control': '#0072b2', 'treated': '#d55e00'}


def _panel(**options):
    i.use_theme('nature')
    p = i.plot.panel(50, 30, x=(0, 10), y=(0, 10))
    p.line([(0, 2), (10, 4)], stroke=COLOURS['control'], name='control')
    p.line([(0, 5), (10, 8)], stroke=COLOURS['treated'], name='treated')
    p.label_lines(**options)
    return p.build()


def _parts(root):
    placed = resolve(root)
    names = {n.prim.text: placed[n.id].bbox for n in root.walk() if n.kind == LINE_LABEL_KIND}
    fills = {n.prim.text: placed[n.id].style.text_fill or placed[n.id].style.fill
             for n in root.walk() if n.kind == LINE_LABEL_KIND}
    swatches = [(placed[n.id].bbox, placed[n.id].style.stroke) for n in root.walk()
                if n.kind == LINE_SWATCH_KIND]
    return names, fills, swatches


def test_swatch_labels_are_ink_with_a_coloured_line_before_each_name():
    root = _panel(color=False, swatch=True)
    names, fills, swatches = _parts(root)
    ink = i.theme('nature').ink
    assert set(names) == {'control', 'treated'}
    # No fill of their own: the names are set in the theme's ink.
    assert all(f is None or f.lower() == ink.lower() for f in fills.values())
    assert sorted(s for _, s in swatches) == sorted(COLOURS.values())
    for box, stroke in swatches:
        name = next(n for n, c in COLOURS.items() if c == stroke)
        label = names[name]
        assert box.x1 < label.x0 and box.y0 <= label.center.y <= box.y1 + 0.5
    assert not [d for d in i.lint(root) if d.severity == 'error']


def test_coloured_names_have_no_swatch_by_default():
    _, _, swatches = _parts(_panel())
    assert swatches == []


def test_quick_direct_ink_legend_uses_swatches():
    rows = [{'x': x, 'y': x * k, 'g': g} for k, g in ((1, 'control'), (2, 'treated')) for x in range(5)]
    chart = i.line(rows, x='x', y='y', color='g', legend='direct-ink', style='scientific.nature')
    (step,) = [s for s in chart.plot()._steps if s[1] == 'label_lines']
    assert step[3] == {'color': False, 'swatch': True}
    with pytest.raises(ValueError, match='direct-ink'):
        i.line(rows, x='x', y='y', color='g', legend='direct-blue')


def test_a_dashed_curve_gets_a_dashed_swatch():
    i.use_theme('nature')
    p = i.plot.panel(50, 30, x=(0, 10), y=(0, 10))
    p.line([(0, 2), (10, 4)], stroke=COLOURS['control'], name='control')
    p.line([(0, 5), (10, 8)], stroke=COLOURS['treated'], stroke_dash=(1.0, 0.8), name='treated')
    p.label_lines(color=False, swatch=True)
    root = p.build()
    placed = resolve(root)
    dashes = {placed[n.id].style.stroke: placed[n.id].style.stroke_dash for n in root.walk()
              if n.kind == LINE_SWATCH_KIND}
    assert dashes[COLOURS['treated']] and not dashes[COLOURS['control']]


def test_a_curve_with_markers_shows_its_marker_on_the_swatch():
    rows = [{'x': x, 'y': x * k, 'g': g} for k, g in ((1, 'control'), (2, 'treated')) for x in range(5)]
    chart = i.line(rows, x='x', y='y', color='g', legend='direct-ink', markers=True, marker='square',
                   style='scientific.nature')
    root = chart.compile().root
    swatches = [n for n in root.walk() if n.kind == LINE_SWATCH_KIND]
    lines = [n for n in swatches if n.prim is not None]
    squares = [m for n in swatches for m in n.walk() if type(m.prim).__name__ == 'RectPrim']
    # Each name has its line and, on it, the curve's square marker.
    assert len(lines) == 2 and len(squares) == 2
