"""inklet.plot: the ramp and colour scale a matrix uses when none is given."""

from __future__ import annotations

import pytest

import inklet as i
from inklet.core import DiagramError, RectPrim, resolve
from inklet.draw.coords import as_drawn
from inklet.plot import panel, ramp
from inklet.plot.ramp import DIVERGING, SEQUENTIAL, default_ramp
from inklet.themes import MAGMA, TOL_BURD, palette, to_lab


def fills(p):
    return [q.style.fill for q in resolve(as_drawn(p.build())).values()
            if isinstance(q.diagram.prim, RectPrim) and q.diagram.kind == 'mark']


def test_default_ramps_are_published_palettes():
    assert palette('magma') is MAGMA and palette('tol-burd') is TOL_BURD
    assert MAGMA.colors[0] == '#000004' and MAGMA.colors[-1] == '#fcfdbf'
    assert TOL_BURD.colors[4] == '#f7f7f7'
    assert default_ramp() is SEQUENTIAL and default_ramp(True) is DIVERGING


def test_sequential_default_runs_light_to_dark_at_a_steady_rate():
    lightness = [to_lab(SEQUENTIAL(t / 10))[0] for t in range(11)]
    assert all(a > b for a, b in zip(lightness, lightness[1:]))
    assert lightness[0] - lightness[-1] > 80
    steps = [a - b for a, b in zip(lightness, lightness[1:])]
    assert max(steps) < 2 * min(steps)


def test_one_sided_data_get_the_sequential_ramp_over_their_extent():
    p = panel(20, 10).matrix([[2, 5], [8, 3]])
    assert p._ramp is SEQUENTIAL
    assert p._scale_domain.domain == (2, 8)
    assert fills(p)[0] == SEQUENTIAL(0) and fills(p)[2] == SEQUENTIAL(1)


def test_data_across_zero_get_a_diverging_ramp_centred_on_zero():
    p = panel(20, 10).matrix([[-1, 0], [3, None]], missing='#dddddd')
    assert p._ramp is DIVERGING
    assert p._scale_domain.domain == (-3, 3)
    assert fills(p)[1] == DIVERGING(.5)


def test_center_selects_the_diverging_ramp_and_centres_the_scale():
    p = panel(20, 10).matrix([[1, 2], [4, 9]], center=4)
    assert p._ramp is DIVERGING
    assert p._scale_domain.domain == (-1, 9)


def test_an_explicit_scale_across_zero_selects_the_diverging_ramp():
    p = panel(20, 10).matrix([[.2, .8]], scale=i.linear((-1, 1)))
    assert p._ramp is DIVERGING and p._scale_domain.domain == (-1, 1)


def test_an_explicit_ramp_keeps_its_fractional_values():
    shades = ramp(['white', 'black'])
    p = panel(20, 10).matrix([[0, 1]], ramp=shades)
    assert p._ramp is shades and p._scale_domain is None
    assert fills(p) == [shades(0), shades(1)]


def test_colorbar_reads_the_default_scale():
    p = panel(20, 10).matrix([[2, 5], [8, 3]]).colorbar(side='bottom')
    assert p.build().bbox is not None


def test_center_and_scale_together_are_refused():
    with pytest.raises(DiagramError, match='center= or scale='):
        panel(20, 10).matrix([[1, 2]], center=1, scale=i.linear((0, 2)))
    with pytest.raises(DiagramError, match='finite'):
        panel(20, 10).matrix([[1, 2]], center=float('nan'))
    with pytest.raises(DiagramError, match='every cell is missing'):
        panel(20, 10).matrix([[None]], missing='#dddddd')
