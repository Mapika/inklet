"""Statistical boundaries and sample ownership, independent of drawing."""

from __future__ import annotations

import math

import pytest

from inklet.plot import box_stats, histogram, kde, quantile


@pytest.mark.parametrize("values,edges,counts", [
    ([-1, 0, .5, 1, 2, 3, 9, 10, 11], [0, 1, 3, 10], (2, 2, 3)),
    ([-math.inf, -1, 0, 1, math.inf], [-1, 1], (3,)),
    ([0, math.nextafter(1, -math.inf), 1, math.nextafter(1, math.inf),
      math.nextafter(3, -math.inf), 3, math.nextafter(3, math.inf), 10],
     [0, 1, 3, 10], (2, 3, 3)),
    ([-math.inf, -1, 0, 1, math.inf], [-math.inf, 0, math.inf], (2, 3)),
])
def test_histogram_boundary_ownership(values, edges, counts):
    found_edges, found_counts = histogram(values, edges)
    assert found_edges == tuple(edges)
    assert found_counts == counts


def test_density_uses_each_bins_width_and_only_counted_observations():
    edges, heights = histogram([-1, 0, 1, 3, 10, 11], [0, 1, 3, 10], density=True)
    assert heights == pytest.approx((1 / 4, 1 / 8, 1 / 14))
    assert sum(h * (b - a) for h, a, b in zip(heights, edges, edges[1:])) == 1


@pytest.mark.parametrize("values,edges,counts", [
    ([0, math.nan, 1, 2], [0, 1, 2], (2, 2)),
    ([-1, 0, .5, 1, 2, 3, math.nan], [0, math.nan, 2], (5, 0)),
    ([math.nan, -1, 0, 1, 2, 3], [math.nan, 1, 2], (3, 2)),
    ([-1, 0, 1, 2, math.nan], [0, 1, math.nan], (2, 2)),
])
def test_histogram_retains_existing_nan_counting(values, edges, counts):
    # Compatibility coverage: this refactor does not introduce a missing-data policy.
    assert histogram(values, edges)[1] == counts


@pytest.mark.parametrize("whisker", [0, 1.5, math.inf])
def test_summary_and_density_leave_the_sample_in_input_order(whisker):
    values = [9, 1, 4, 2, 100, 3, 8, 5, 7, 6]
    original = values.copy()
    stats = box_stats(values, whisker=whisker)
    assert (stats.q1, stats.median, stats.q3) == (3.25, 5.5, 7.75)
    assert stats.count == 10
    assert quantile(values, .5) == 5.5
    assert kde(values, [0, 5, 10]) == kde(tuple(values), [0, 5, 10])
    assert values == original
