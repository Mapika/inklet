"""legend='best' in a cell too narrow for a key beside the plot: the key goes
below the plot, with a warning, instead of the figure being refused."""
import math
import warnings

import pytest

import inklet as i

ROWS = [{'x': x, 'y': math.sin(x / 3 + k) + k * 0.1, 'g': name}
        for k, name in enumerate(['baseline model', 'pruned circuit', 'random ablation'])
        for x in range(30)]


def _chart():
    return i.line(ROWS, x='x', y='y', color='g', legend='best', style='scientific.nature')


def _row(count):
    return i.Layout('row', [_chart() for _ in range(count)], width='double', style='scientific.nature')


def test_a_best_key_with_no_room_beside_a_narrow_plot_goes_below_it():
    with pytest.warns(UserWarning, match="legend='best'.*below the plot"):
        figure = _row(4).compile()
    assert not [d.code for d in figure.lint() if d.severity == 'error']
    assert _key_under_ticks(figure)


def _key_under_ticks(figure):
    """Whether every key name is set lower on the page than every tick number."""
    from inklet.core import resolve
    from inklet.plot.axis import TICK_LABEL_KIND
    from inklet.plot.key import LEGEND_LABEL_KIND
    placed = resolve(figure.root)
    tops = {kind: [placed[n.id].bbox.y0 for n in figure.root.walk() if n.kind == kind]
            for kind in (LEGEND_LABEL_KIND, TICK_LABEL_KIND)}
    return tops[LEGEND_LABEL_KIND] and min(tops[LEGEND_LABEL_KIND]) > max(tops[TICK_LABEL_KIND])


def test_a_best_key_that_fits_beside_the_plot_stays_there():
    with warnings.catch_warnings():
        warnings.simplefilter('error', UserWarning)
        warnings.filterwarnings('ignore', category=i.LayoutWarning)
        figure = _row(3).compile()
    assert not _key_under_ticks(figure)


def test_a_key_that_fits_nowhere_still_raises_the_first_error():
    rows = [dict(r, g=r['g'] * 6) for r in ROWS]
    chart = i.line(rows, x='x', y='y', color='g', legend='best', style='scientific.nature')
    layout = i.Layout('row', [chart, _chart(), _chart(), _chart()], width='double', style='scientific.nature')
    with pytest.raises(i.LayoutError):
        layout.compile()
