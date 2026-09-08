"""Numeric axes preserve distinct data positions and readable measured labels."""
import math

import pytest

from inklet.core import resolve
from inklet.draw.coords import as_drawn
from inklet.plot import axis, linear, tick_values
from inklet.plot.axis import TICK_LABEL_KIND
from inklet.plot.scale import format_number, nice_bounds, nice_ticks, si_labels


@pytest.mark.parametrize('base,step', [
    (1e6, 1), (-1e6, 1), (1e8, .25), (1e-6, 1e-12),
    (1e12, .1), (-1e12, .1), (1e-15, 1e-21),
])
def test_scientific_labels_distinguish_resolved_positions(base, step):
    values = tuple(base + j * step for j in range(6))
    labels = linear((values[0], values[-1])).tick_labels(values)
    assert len(set(labels)) == len(values)
    for value, label in zip(values, labels):
        assert abs(float(label) - value) <= math.ulp(value)


@pytest.mark.parametrize('step', [1e-13, 1e-15, 2e-18, 5e-21, 1e-24, 1e-100])
@pytest.mark.parametrize('reverse', [False, True])
def test_small_ticks_are_distinct_and_remain_on_their_lattice(step, reverse):
    bounds = (0, 5 * step)
    ticks = nice_ticks(*(bounds[::-1] if reverse else bounds))
    assert len(ticks) == 6
    assert len(set(ticks)) == 6
    assert [value / step for value in ticks] == pytest.approx(range(6))
    assert linear(bounds, (0, 100)).positions(ticks) == pytest.approx(
        [0, 20, 40, 60, 80, 100])
    assert len(set(linear(bounds).tick_labels(ticks))) == 6
    assert len(set(si_labels(ticks))) == 6


@pytest.mark.parametrize('bounds', [
    (1e12, 1e12 + .5), (-1e12, -1e12 + .5),
    (1e12 + .5, 1e12),
])
def test_representable_narrow_domains_keep_multiple_ticks(bounds):
    ticks = nice_ticks(*bounds)
    assert len(ticks) == 6
    assert len(set(ticks)) == 6
    assert min(bounds) <= ticks[0] < ticks[-1] <= max(bounds)


@pytest.mark.parametrize('bounds', [(1e12 + .03, 1e12 + .48), (1e-15, 4.8e-15)])
def test_nice_bounds_expand_small_spans_to_round_numbers(bounds):
    lo, hi = nice_bounds(*bounds)
    assert lo <= bounds[0] and hi >= bounds[1]
    assert hi > lo
    assert len(nice_ticks(lo, hi)) >= 4


@pytest.mark.parametrize('side', ['bottom', 'top', 'left', 'right'])
@pytest.mark.parametrize('bounds', [(1e6, 1e6 + 5), (1e12, 1e12 + .5), (0, 5e-15)])
def test_precision_aware_tick_labels_are_measured_before_thinning(side, bounds):
    horizontal = side in ('bottom', 'top')
    scale = linear(bounds, (0, 85 if horizontal else -45))
    node = axis(scale, side=side)
    labels = [p.bbox for p in resolve(as_drawn(node)).values()
              if p.diagram.kind == TICK_LABEL_KIND]
    kept = tick_values(scale, horizontal=horizontal)
    assert len(labels) == len(kept) >= 2
    for a, b in zip(labels, labels[1:]):
        assert (a.x1 <= b.x0 or b.x1 <= a.x0 or
                a.y1 <= b.y0 or b.y1 <= a.y0)


@pytest.mark.parametrize('bounds,expected', [
    ((0, 1), ('0.0', '0.2', '0.4', '0.6', '0.8', '1.0')),
    ((1, 1.5), ('1.0', '1.1', '1.2', '1.3', '1.4', '1.5')),
    ((0, 500), ('0', '100', '200', '300', '400', '500')),
    ((0, 5e6), ('0', '1e6', '2e6', '3e6', '4e6', '5e6')),
    ((0, 5e-6), ('0', '1e-6', '2e-6', '3e-6', '4e-6', '5e-6')),
])
def test_ordinary_axis_labels_keep_existing_format(bounds, expected):
    scale = linear(bounds)
    assert scale.tick_labels(scale.ticks()) == expected


def test_single_value_and_unresolved_roundoff_keep_existing_behavior():
    assert nice_ticks(1e12, 1e12) == (1e12,)
    assert format_number(-1e-7, .1) == '0.0'
    assert format_number(2.5e-6) == '2.5e-6'
    assert format_number(5e-324, 5e-324) == '4.941e-324'


@pytest.mark.parametrize('base', [1., -1., 1e16, -1e16, 1e100, -1e100,
                                 1e-100, -1e-100, 1e308, -1e308,
                                 1e-300, -1e-300, 1e-308, -1e-308, 0.])
@pytest.mark.parametrize('ulps', [1, 2, 5])
@pytest.mark.parametrize('reverse', [False, True])
def test_ticks_at_float_resolution_are_unique_and_inside_domain(base, ulps, reverse):
    hi = base
    for _ in range(ulps):
        hi = math.nextafter(hi, math.inf)
    bounds = (base, hi)
    ticks = nice_ticks(*(bounds[::-1] if reverse else bounds))
    assert ticks
    assert len(set(ticks)) == len(ticks)
    assert all(base <= value <= hi for value in ticks)
    assert all(a < b for a, b in zip(ticks, ticks[1:]))
    lo_nice, hi_nice = nice_bounds(*bounds)
    assert lo_nice <= base and hi_nice >= hi
