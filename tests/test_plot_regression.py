"""Regression, residuals, QQ/PP and Bland-Altman: numbers against references."""

import math
import random
import re
import statistics

import pytest

import inklet
from inklet.core import DiagramError
from inklet.diagnostics import lint
from inklet.plot import (bland_altman, linear_fit, lowess, plotting_positions,
                         pp_points, qq_line, qq_points, t_cdf, t_quantile)
from inklet import use_theme


@pytest.fixture(autouse=True)
def _nature():
    use_theme("nature")


# R's `cars` data set.
SPEED = [4, 4, 7, 7, 8, 9, 10, 10, 10, 11, 11, 12, 12, 12, 12, 13, 13, 13, 13, 14,
         14, 14, 14, 15, 15, 15, 16, 16, 17, 17, 17, 18, 18, 18, 18, 19, 19, 19, 20,
         20, 20, 20, 20, 22, 23, 24, 24, 24, 24, 25]
DIST = [2, 10, 4, 22, 16, 10, 18, 26, 34, 17, 28, 14, 20, 24, 28, 26, 34, 34, 46,
        26, 36, 60, 80, 20, 26, 54, 32, 40, 32, 40, 50, 42, 56, 76, 84, 36, 46, 68,
        32, 48, 52, 56, 64, 66, 54, 70, 92, 93, 120, 85]
CARS = list(zip(SPEED, DIST))


def _svg(node):
    return re.sub(r'id="[^"]*"', "", inklet.to_svg(node))


# -- Student's t ---------------------------------------------------------------

def test_t_quantiles_match_tables():
    assert t_quantile(0.975, 10) == pytest.approx(2.228138851986274, abs=1e-10)
    assert t_quantile(0.975, 48) == pytest.approx(2.010634757624228, abs=1e-9)
    assert t_quantile(0.5, 7) == pytest.approx(0.0, abs=1e-12)
    assert t_cdf(0.0, 3) == pytest.approx(0.5)
    assert t_cdf(2.228138851986274, 10) == pytest.approx(0.975, abs=1e-12)


def test_t_matches_scipy_over_a_range():
    stats = pytest.importorskip("scipy.stats")
    for df in (1, 2, 5, 30, 200):
        for p in (0.6, 0.9, 0.995):
            assert t_quantile(p, df) == pytest.approx(stats.t.ppf(p, df), rel=1e-8)


# -- linear fit: R's lm(dist ~ speed, cars) --------------------------------------

def test_linear_fit_matches_r_lm_on_cars():
    fit = linear_fit(CARS)
    assert fit.slope == pytest.approx(3.932408759124087, rel=1e-12)
    assert fit.intercept == pytest.approx(-17.579094890510948, rel=1e-12)
    assert fit.r2 == pytest.approx(0.6510793807582509, rel=1e-12)
    assert fit.sigma == pytest.approx(15.37958674881991, rel=1e-12)
    assert fit.slope_se == pytest.approx(0.4155127766571223, rel=1e-10)
    assert fit.intercept_se == pytest.approx(6.758440169379237, rel=1e-10)
    assert fit.p == pytest.approx(1.489836496e-12, rel=1e-6)
    assert fit.n == 50


def test_confidence_and_prediction_bands_match_r_predict():
    # predict(lm(dist ~ speed, cars), data.frame(speed = 21), interval = ...)
    fit = linear_fit(CARS)
    lo, hi = fit.band(21)
    assert (lo, hi) == pytest.approx((58.59745, 71.40563), abs=1e-4)
    lo, hi = fit.band(21, prediction=True)
    assert (lo, hi) == pytest.approx((33.42258, 96.58050), abs=1e-4)


def test_linear_fit_matches_scipy_linregress():
    stats = pytest.importorskip("scipy.stats")
    rng = random.Random(3)
    pts = [(x, 2 - 0.4 * x + rng.gauss(0, 1)) for x in (rng.uniform(0, 10) for _ in range(40))]
    ref = stats.linregress([p[0] for p in pts], [p[1] for p in pts])
    fit = linear_fit(pts)
    assert fit.slope == pytest.approx(ref.slope, rel=1e-10)
    assert fit.intercept == pytest.approx(ref.intercept, rel=1e-10)
    assert fit.r2 == pytest.approx(ref.rvalue ** 2, rel=1e-10)
    assert fit.p == pytest.approx(ref.pvalue, rel=1e-6)
    assert fit.slope_se == pytest.approx(ref.stderr, rel=1e-10)


def test_linear_fit_needs_two_points_and_spread():
    with pytest.raises(DiagramError):
        linear_fit([(0, 1)])
    with pytest.raises(DiagramError):
        linear_fit([(1, 1), (1, 2), (1, 3)])


# -- lowess: R's lowess(cars) ----------------------------------------------------

def test_lowess_matches_r_on_cars():
    r = [4.965459, 4.965459, 13.124495, 13.124495, 15.858633, 18.579691,
         21.280313, 21.280313, 21.280313, 24.129277, 24.129277, 27.119549,
         27.119549, 27.119549, 27.119549, 30.027276, 30.027276, 30.027276,
         30.027276, 32.962506, 32.962506, 32.962506, 32.962506, 36.757728,
         36.757728, 36.757728, 40.435075, 40.435075, 43.463492, 43.463492,
         43.463492, 46.885479, 46.885479, 46.885479, 46.885479, 50.793152,
         50.793152, 50.793152, 56.491224, 56.491224, 56.491224, 56.491224,
         56.491224, 67.585824, 73.079695, 78.643164, 78.643164, 78.643164,
         78.643164, 84.328698]
    out = lowess(CARS)
    assert [x for x, _ in out] == [float(s) for s in SPEED]
    assert [y for _, y in out] == pytest.approx(r, abs=1e-6)


def test_lowess_is_exact_on_a_line():
    pts = [(x, 3 * x + 1) for x in range(20)]
    assert [y for _, y in lowess(pts, frac=0.3)] == pytest.approx([3 * x + 1 for x in range(20)])


# -- QQ and PP ---------------------------------------------------------------------

def test_plotting_positions_follow_r_ppoints():
    assert plotting_positions(5) == pytest.approx([(i - 3 / 8) / (5 + 1 - 3 / 4) for i in range(1, 6)])
    assert plotting_positions(20) == pytest.approx([(i - 0.5) / 20 for i in range(1, 21)])


def test_qq_points_and_quartile_line_match_r():
    rng = random.Random(5)
    values = [rng.gauss(10, 2) for _ in range(40)]
    pts = qq_points(values)
    nd = statistics.NormalDist()
    ordered = sorted(values)
    for k, (x, y) in enumerate(pts):
        assert x == pytest.approx(nd.inv_cdf((k + 0.5) / 40))
        assert y == ordered[k]
    # qqline: through the type-7 quartiles of the sample and of the normal
    q1, q3 = statistics.quantiles(values, n=4, method="inclusive")[0::2]
    z1, z3 = nd.inv_cdf(0.25), nd.inv_cdf(0.75)
    intercept, slope = qq_line(values)
    assert slope == pytest.approx((q3 - q1) / (z3 - z1))
    assert intercept == pytest.approx(q1 - slope * z1)
    assert qq_line(values, line="identity") == (0.0, 1.0)
    i2, s2 = qq_line(values, line="fit")
    assert (i2, s2) == pytest.approx((statistics.fmean(values), statistics.stdev(values)))


def test_qq_against_another_distribution():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    pts = qq_points(values, statistics.NormalDist(5, 3))
    assert pts[0][0] == pytest.approx(statistics.NormalDist(5, 3).inv_cdf((1 - 0.5) / 12))


def test_pp_points_are_probabilities_in_order():
    rng = random.Random(9)
    pts = pp_points([rng.gauss(0, 1) for _ in range(50)])
    assert all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts)
    assert [x for x, _ in pts] == sorted(x for x, _ in pts)
    assert [y for _, y in pts] == pytest.approx(plotting_positions(50))


# -- Bland-Altman --------------------------------------------------------------------

def test_bland_altman_numbers():
    a = [10.0, 12.0, 9.0, 15.0, 11.0]
    b = [9.0, 12.5, 8.0, 13.0, 11.5]
    d = [x - y for x, y in zip(a, b)]
    ag = bland_altman(a, b, confidence=0.95)
    bias, sd = statistics.fmean(d), statistics.stdev(d)
    assert ag.bias == pytest.approx(bias)
    assert ag.sd == pytest.approx(sd)
    assert (ag.lower, ag.upper) == pytest.approx((bias - 1.96 * sd, bias + 1.96 * sd))
    t = t_quantile(0.975, 4)
    assert ag.bias_ci == pytest.approx((bias - t * sd / math.sqrt(5), bias + t * sd / math.sqrt(5)))
    half = t * math.sqrt(3 * sd * sd / 5)
    assert ag.upper_ci == pytest.approx((ag.upper - half, ag.upper + half))
    assert ag.points[0] == (9.5, 1.0)


def test_bland_altman_percent_and_errors():
    ag = bland_altman([110, 90], [90, 110], percent=True)
    assert [p[1] for p in ag.points] == pytest.approx([20.0, -20.0])
    with pytest.raises(DiagramError):
        bland_altman([1, 2], [1])
    with pytest.raises(DiagramError):
        bland_altman([1], [1])


# -- drawing ------------------------------------------------------------------------

def _cars_panel():
    p = inklet.panel(50, 36, x=(0, 26), y=(-20, 125))
    return p.regression(CARS).axis("bottom", label="Speed").axis("left", label="Distance")


def test_regression_draws_lint_clean_and_notes_the_fit():
    p = _cars_panel()
    node = p.build()
    assert lint(node) == []
    notes = [n.notes["regression"] for n in _walk(node) if "regression" in n.notes]
    assert notes and notes[0]["slope"] == pytest.approx(3.9324087591)
    assert inklet.to_pdf(node)[:4] == b"%PDF"


def test_regression_is_deterministic():
    assert _svg(_cars_panel().build()) == _svg(_cars_panel().build())


def test_lowess_regression_and_residuals_draw():
    p = inklet.panel(50, 36, x=(0, 26), y=(-20, 125))
    p.regression(CARS, method="lowess", scatter=False)
    q = inklet.panel(50, 36, x=(0, 26), y=(-40, 50))
    q.residuals(CARS, smooth=True).axis("bottom").axis("left")
    assert lint(inklet.row([p.axis("bottom").axis("left"), q])) == []
    with pytest.raises(DiagramError):
        inklet.panel(10, 10, x=(0, 1), y=(0, 1)).regression(CARS, method="cubic")


def test_regression_on_a_log_x_axis_fits_in_log_units():
    pts = [(10 ** (k / 5), 2 * k / 5 + 1) for k in range(1, 16)]
    p = inklet.panel(40, 30, x=inklet.plot.log((1, 1000)), y=(0, 8))
    p.regression(pts).axis("bottom").axis("left")
    node = p.build()
    note = [n.notes["regression"] for n in _walk(node) if "regression" in n.notes][0]
    assert note["slope"] == pytest.approx(2.0)
    assert lint(node) == []


def test_qq_pp_and_bland_altman_panels_are_lint_clean():
    rng = random.Random(2)
    values = [rng.gauss(0, 1) for _ in range(80)]
    q = inklet.panel(36, 36, x=(-3, 3), y=(-3, 3)).qq(values).axis("bottom").axis("left")
    pp = inklet.panel(36, 36, x=(0, 1), y=(0, 1)).pp(values).axis("bottom").axis("left")
    truth = [rng.uniform(50, 150) for _ in range(60)]
    m1 = [t + rng.gauss(0, 4) for t in truth]
    m2 = [t + rng.gauss(1, 4) for t in truth]
    ba = inklet.panel(50, 36, x=(40, 160), y=(-20, 20))
    ba.bland_altman(m1, m2, confidence=0.95, format="{:.1f}").axis("bottom").axis("left")
    fig = inklet.row([q, pp, ba])
    assert lint(fig) == []
    svg = inklet.to_svg(fig)
    assert "Mean" in svg or "M" in svg


def test_bland_altman_labels_sit_in_the_margin():
    a = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    b = [1.1, 1.8, 3.3, 3.9, 5.2, 5.7]
    p = inklet.panel(40, 30, x=(0, 7), y=(-1, 1)).bland_altman(a, b)
    labels = [n for n in p.build().children if n.kind == "label"]
    assert len(labels) == 1
    assert labels[0].bbox.x0 >= p.area.x1


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)
