"""Kernel densities (1D and 2D), hexbin, 2D histograms and density scatter."""

import math
import random
import re
import statistics

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError
from inklet.diagnostics import lint
from inklet.plot import (histogram2d, kde2d, kde_bandwidth, kde_curve,
                         mass_levels, point_density)


@pytest.fixture(autouse=True)
def _nature():
    use_theme("nature")


def _svg(node):
    return re.sub(r'id="[^"]*"', "", inklet.to_svg(node))


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _notes(node, key):
    return [n.notes[key] for n in _walk(node) if key in n.notes]


def sample(n=300, seed=1, mu=0.0, sd=1.0):
    rng = random.Random(seed)
    return [rng.gauss(mu, sd) for _ in range(n)]


def cloud(n=1500, seed=2):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        x = rng.gauss(0, 1.2)
        out.append((x, 0.6 * x + rng.gauss(0, 0.8)))
    return out


# -- bandwidth rules: R's bw.nrd and bw.nrd0 -------------------------------------

def _iqr(values):
    q = statistics.quantiles(values, n=4, method="inclusive")
    return q[2] - q[0]


def test_scott_and_silverman_follow_r():
    values = sample(200, seed=4)
    sd, iqr, n = statistics.stdev(values), _iqr(values), len(values)
    assert kde_bandwidth(values, "scott") == pytest.approx(
        1.06 * min(sd, iqr / 1.34) * n ** -0.2)
    assert kde_bandwidth(values, "silverman") == pytest.approx(
        0.9 * min(sd, iqr / 1.34) * n ** -0.2)
    assert kde_bandwidth(values, 0.5, adjust=2) == pytest.approx(1.0)
    assert kde_bandwidth(values, "scott", adjust=0.5) == pytest.approx(
        0.5 * kde_bandwidth(values, "scott"))


def test_bandwidth_of_constant_data_falls_back():
    assert kde_bandwidth([3.0, 3.0, 3.0]) > 0
    with pytest.raises(DiagramError):
        kde_bandwidth([1, 2, 3], "sheather")


def test_kde_curve_is_the_gaussian_mixture_and_integrates_to_one():
    values = sample(100, seed=6)
    h = 0.4
    grid, dens = kde_curve(values, bandwidth=h, samples=400, cut=4)
    x = grid[123]
    direct = sum(math.exp(-0.5 * ((x - v) / h) ** 2) for v in values) / (
        len(values) * h * math.sqrt(2 * math.pi))
    assert dens[123] == pytest.approx(direct, rel=1e-12)
    step = grid[1] - grid[0]
    assert sum(dens) * step == pytest.approx(1.0, abs=2e-3)
    assert grid[0] == pytest.approx(min(values) - 4 * h)


def test_kde_curve_matches_scipy_with_the_same_bandwidth():
    stats = pytest.importorskip("scipy.stats")
    values = sample(80, seed=7)
    h = kde_bandwidth(values)
    ref = stats.gaussian_kde(values, bw_method=h / statistics.stdev(values))
    grid, dens = kde_curve(values, bandwidth=h, samples=50)
    assert list(dens) == pytest.approx(list(ref(grid)), rel=1e-9)


def test_kde_panel_groups_fill_and_notes():
    groups = {"control": sample(200, 1, 4, 1), "treated": sample(150, 2, 6, 1.3)}
    p = inklet.panel(50, 32, x=(0, 12), y=(0, 0.5))
    p.kde(groups, fill=True).axis("bottom").axis("left").legend()
    node = p.build()
    assert lint(node) == []
    assert [k.name for k in p.keys] == ["control", "treated"]
    note = _notes(node, "kde")[0]
    assert len(note["groups"]) == 2


def test_kde_count_stat_and_horizontal_orientation():
    values = sample(100)
    p = inklet.panel(30, 30, x=(0, 60), y=(-4, 4))
    p.kde(values, stat="count", orient="h").axis("bottom").axis("left")
    assert lint(p.build()) == []
    with pytest.raises(DiagramError):
        inklet.panel(10, 10, x=(0, 1), y=(0, 1)).kde(values, stat="mass")


def test_kde_on_a_log_axis_is_estimated_per_decade():
    values = [10 ** v for v in sample(400)]
    p = inklet.panel(40, 30, x=inklet.plot.log((0.001, 1000)), y=(0, 0.5))
    p.kde(values).axis("bottom").axis("left")
    node = p.build()
    assert lint(node) == []
    note = _notes(node, "kde")[0]
    assert note["log"] is True
    # standard normal in log10 units: peak near 1/sqrt(2 pi)
    assert note["peak"][0] == pytest.approx(0.3989, abs=0.04)


def test_kde_is_deterministic():
    def build():
        p = inklet.panel(40, 30, x=(-4, 4), y=(0, 0.5))
        return p.kde({"a": sample(50, 1), "b": sample(50, 2, 1)}, fill=True).build()
    assert _svg(build()) == _svg(build())


# -- 2D KDE ----------------------------------------------------------------------

def test_kde2d_integrates_to_one_and_matches_direct_sum():
    pts = cloud(400)
    dens = kde2d(pts, gridsize=64)
    dx = dens.xs[1] - dens.xs[0]
    dy = dens.ys[1] - dens.ys[0]
    total = sum(v for row in dens.values for v in row) * dx * dy
    assert total == pytest.approx(1.0, abs=0.01)
    hx, hy = dens.bandwidth
    x, y = 0.3, -0.2
    direct = sum(math.exp(-0.5 * (((x - a) / hx) ** 2 + ((y - b) / hy) ** 2))
                 for a, b in pts) / (len(pts) * 2 * math.pi * hx * hy)
    # binned estimate against the exact sum: linear binning errs by well under 2%
    assert dens.at(x, y) == pytest.approx(direct, rel=0.02)


def test_kde2d_bandwidth_is_scott_per_axis():
    pts = cloud(500)
    dens = kde2d(pts)
    n = len(pts)
    sx = statistics.stdev(p[0] for p in pts)
    sy = statistics.stdev(p[1] for p in pts)
    assert dens.bandwidth == pytest.approx((sx * n ** (-1 / 6), sy * n ** (-1 / 6)))


def test_mass_levels_enclose_their_mass():
    dens = kde2d(cloud(800), gridsize=80)
    flat = [v for row in dens.values for v in row]
    total = sum(flat)
    for mass, level in zip((0.5, 0.9), mass_levels(dens, (0.5, 0.9))):
        inside = sum(v for v in flat if v >= level) / total
        assert inside == pytest.approx(mass, abs=0.01)
    with pytest.raises(DiagramError):
        mass_levels(dens, (1.5,))


def test_kde2d_panels_lines_and_filled_are_lint_clean():
    pts = cloud(600)
    p = inklet.panel(40, 40, x=(-4, 4), y=(-4, 4))
    p.kde2d(pts, levels=(0.5, 0.8, 0.95)).axis("bottom").axis("left")
    q = inklet.panel(40, 40, x=(-4, 4), y=(-4, 4))
    q.kde2d(pts, levels=5, fill=True).axis("bottom").axis("left")
    fig = inklet.row([p, q])
    assert lint(fig) == []
    note = _notes(q.build(), "kde2d")[0]
    assert len(note["masses"]) == 5


def test_kde2d_is_deterministic():
    def build():
        return inklet.panel(30, 30, x=(-4, 4), y=(-4, 4)).kde2d(cloud(300), fill=True).build()
    assert _svg(build()) == _svg(build())


# -- 2D histogram and hexbin ----------------------------------------------------

def test_histogram2d_matches_numpy():
    np = pytest.importorskip("numpy")
    pts = cloud(700)
    xe = [-4 + 0.5 * k for k in range(17)]
    ye = [-3 + 0.75 * k for k in range(9)]
    ex, ey, counts = histogram2d(pts, (xe, ye))
    ref, _, _ = np.histogram2d([p[0] for p in pts], [p[1] for p in pts], bins=[xe, ye])
    # counts are [row j (y)][column i (x)]
    for i in range(len(xe) - 1):
        for j in range(len(ye) - 1):
            assert counts[j][i] == ref[i][j]


def test_histogram2d_density_and_log_bins():
    pts = [(10 ** random.Random(k).uniform(0, 3), 1.0 + k % 5) for k in range(500)]
    xe, ye, dens = histogram2d(pts, 6, density=True,
                               x_scale=inklet.plot.log((1, 1000)))
    ratios = [xe[k + 1] / xe[k] for k in range(len(xe) - 1)]
    assert max(ratios) == pytest.approx(min(ratios))
    area = sum(dens[j][i] * (xe[i + 1] - xe[i]) * (ye[j + 1] - ye[j])
               for j in range(len(ye) - 1) for i in range(len(xe) - 1))
    assert area == pytest.approx(1.0)


def test_hexbin_and_hist2d_panels_with_colorbars():
    pts = cloud(1500)
    p = inklet.panel(40, 40, x=(-4, 4), y=(-4, 4))
    p.hexbin(pts, gridsize=18).axis("bottom").axis("left").colorbar(label="Count")
    q = inklet.panel(40, 40, x=(-4, 4), y=(-4, 4))
    q.hist2d(pts, bins=16).axis("bottom").axis("left").colorbar(label="Count")
    fig = inklet.row([p, q])
    assert lint(fig) == []
    note = _notes(p.build(), "hexbin")[0]
    assert note["total"] == sum(1 for x, y in pts if -4 <= x <= 4 and -4 <= y <= 4)


def test_hexbin_counts_every_point_on_log_axes():
    rng = random.Random(3)
    pts = [(math.exp(rng.gauss(0, 1)), math.exp(rng.gauss(0, 1))) for _ in range(2000)]
    p = inklet.panel(40, 40, x=inklet.plot.log((0.01, 100)), y=inklet.plot.log((0.01, 100)))
    p.hexbin(pts, log=True).axis("bottom").axis("left").colorbar()
    node = p.build()
    assert lint(node) == []
    assert _notes(node, "hexbin")[0]["total"] == 2000


def test_hexbin_rejects_a_band_axis():
    p = inklet.panel(20, 20, x=["a", "b"], y=(0, 1))
    with pytest.raises(DiagramError):
        p.hexbin([(0, 0)])


# -- density scatter -----------------------------------------------------------

def test_point_density_peaks_in_the_crowd():
    pts = [(0.0, 0.0)] * 50 + [(3.0, 3.0)]
    p = inklet.panel(40, 40, x=(-4, 4), y=(-4, 4))
    kept, dens, h = point_density(p, pts)
    assert len(kept) == 51
    assert max(dens) == 1.0
    assert dens[0] == 1.0 and dens[-1] < 0.1
    assert h > 0


def test_density_scatter_raster_with_1e5_points_on_log_axes():
    rng = random.Random(8)
    pts = [(math.exp(rng.gauss(1, 1)), math.exp(rng.gauss(0.5, 0.8)))
           for _ in range(100_000)]
    p = inklet.panel(40, 40, x=inklet.plot.log((0.01, 1000)),
                     y=inklet.plot.log((0.01, 1000)))
    p.density_scatter(pts, raster=True, size=0.5).axis("bottom").axis("left")
    p.colorbar(label="Relative density")
    node = p.build()
    assert lint(node) == []
    svg = inklet.to_svg(node)
    assert "<image" in svg
    assert len(svg) < 3_000_000
    assert _notes(node, "density_scatter")[0]["points"] == 100_000


def test_density_scatter_vector_is_deterministic():
    def build():
        p = inklet.panel(30, 30, x=(-4, 4), y=(-4, 4))
        return p.density_scatter(cloud(300), size=0.6).build()
    assert _svg(build()) == _svg(build())


def test_plot_spec_round_trip_for_density_plots():
    spec = inklet.plot_spec(x=(-4, 4), y=(-4, 4), height=30)
    spec.hexbin(cloud(400)).kde2d(cloud(400), levels=3)
    doc = inklet.document(width=60)
    doc.add("fig", spec)
    assert "<path" in doc.compile().to_svg()


def test_named_kde_calls_take_separate_series_colors():
    import inklet

    p = inklet.panel(40, 30, x=(0, 10), y=(0, 1))
    p.kde([3, 4, 4.5, 5], name="a").kde([6, 7, 7.5, 8], name="b")
    colors = {key.name: key.color for key in p.keys}
    assert colors["a"] != colors["b"]
