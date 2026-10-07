"""The fit's statistics, the equation written on a regression plot, and the
fits a quick chart keeps by series."""

import math
import random
from fractions import Fraction

import pytest

import inklet
import inklet.quick as i
from inklet import use_theme
from inklet.core import DiagramError
from inklet.diagnostics import lint
from inklet.plot import LinearFit, linear_fit
from inklet.plot.regression import equation_from, equation_text, figure


@pytest.fixture(autouse=True)
def _nature():
    use_theme("nature")


MINUS = "−"

# Anscombe (1973), the four data sets. Set I is the one the textbook quotes:
# slope 0.500, intercept 3.00, R^2 0.667. The same data is in
# examples/published/anscombe_1973/data/anscombe.csv.
ANSCOMBE_X = [10, 8, 13, 9, 11, 14, 6, 4, 12, 7, 5]
ANSCOMBE_I = list(zip(ANSCOMBE_X, [8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68]))
ANSCOMBE_II = list(zip(ANSCOMBE_X, [9.14, 8.14, 8.74, 8.77, 9.26, 8.10, 6.13, 3.10, 9.13, 7.26, 4.74]))
ANSCOMBE_III = list(zip(ANSCOMBE_X, [7.46, 6.77, 12.74, 7.11, 7.81, 8.84, 6.08, 5.39, 8.15, 6.42, 5.73]))
ANSCOMBE_IV = list(zip([8, 8, 8, 8, 8, 8, 8, 19, 8, 8, 8],
                       [6.58, 5.76, 7.71, 8.84, 8.47, 7.04, 5.25, 12.5, 5.56, 7.91, 6.89]))

# qt(0.975, df = 9), from a t table.
T_975_DF9 = 2.2621571627409915
# The two-sided p-value of the slope, by integrating the t density numerically
# (Simpson's rule), which shares no code with the continued fraction.
P_ANSCOMBE_I = 0.002169628872583458


def _walk(node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _notes(node, key):
    return [n.notes[key] for n in _walk(node) if key in n.notes]


# -- the statistics ---------------------------------------------------------------

def test_anscombe_set_one_matches_exact_rational_arithmetic():
    # Fraction("8.04") is the decimal exactly, so this is the fit with no
    # rounding at all.
    xs = [Fraction(x) for x, _ in ANSCOMBE_I]
    ys = [Fraction(str(y)) for _, y in ANSCOMBE_I]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    r2 = sxy * sxy / (sxx * syy)

    fit = linear_fit(ANSCOMBE_I)
    assert fit.n == n == 11
    assert fit.slope == pytest.approx(float(slope), rel=1e-13)
    assert fit.intercept == pytest.approx(float(intercept), rel=1e-12)
    assert fit.r2 == pytest.approx(float(r2), rel=1e-12)
    assert fit.r == pytest.approx(math.sqrt(float(r2)), rel=1e-12)


def test_anscombe_set_one_matches_the_textbook_numbers():
    fit = linear_fit(ANSCOMBE_I)
    assert round(fit.slope, 3) == 0.500
    assert round(fit.intercept, 2) == 3.00
    assert round(fit.r2, 3) == 0.667
    assert fit.r == pytest.approx(0.8164, abs=1e-4)
    assert fit.slope_se == pytest.approx(0.1179, abs=1e-4)
    assert fit.p == pytest.approx(0.00217, abs=1e-5)
    low, high = fit.slope_interval(0.95)
    assert (low, high) == pytest.approx((0.2334, 0.7668), abs=1e-4)


def test_anscombe_slope_p_value_matches_numerical_integration():
    assert linear_fit(ANSCOMBE_I).p == pytest.approx(P_ANSCOMBE_I, rel=1e-9)


def test_the_four_anscombe_sets_share_their_statistics():
    # The point of the quartet: one slope, one R^2, one p-value, four shapes.
    # R^2 is 0.6662, 0.6663 and 0.6667 for sets II to IV.
    for data in (ANSCOMBE_II, ANSCOMBE_III, ANSCOMBE_IV):
        fit = linear_fit(data)
        assert round(fit.slope, 3) == 0.500
        assert fit.r2 == pytest.approx(0.6666, abs=1e-3)
        assert fit.p == pytest.approx(0.0022, abs=1e-4)


def test_slope_interval_is_the_t_quantile_times_the_standard_error():
    fit = linear_fit(ANSCOMBE_I)
    low, high = fit.slope_interval(0.95)
    assert low == pytest.approx(fit.slope - T_975_DF9 * fit.slope_se, abs=1e-9)
    assert high == pytest.approx(fit.slope + T_975_DF9 * fit.slope_se, abs=1e-9)
    narrow = fit.slope_interval(0.5)
    assert narrow[1] - narrow[0] < high - low


def test_slope_interval_needs_three_points_and_a_valid_confidence():
    with pytest.raises(DiagramError):
        linear_fit([(0, 0), (1, 1)]).slope_interval()
    with pytest.raises(DiagramError):
        linear_fit(ANSCOMBE_I).slope_interval(1.0)


def test_a_perfect_line_has_a_p_value_of_zero():
    fit = linear_fit([(x, 2 * x + 1) for x in range(10)])
    assert fit.slope == pytest.approx(2.0)
    assert fit.p < 1e-12
    assert fit.r == pytest.approx(1.0)
    assert fit.r2 == pytest.approx(1.0)


def test_pure_noise_has_a_large_p_value_at_a_fixed_seed():
    rng = random.Random(11)
    fit = linear_fit([(x, 1.0 + rng.gauss(0, 1)) for x in range(30)])
    assert fit.p > 0.05
    assert abs(fit.r) < 0.5


def test_r_is_signed_and_undefined_for_a_flat_y():
    down = linear_fit([(x, 10 - x) for x in range(8)])
    assert down.r == pytest.approx(-1.0)
    assert down.r2 == pytest.approx(1.0)
    assert math.isnan(linear_fit([(x, 3.0) for x in range(5)]).r)


# -- the equation text --------------------------------------------------------------

def test_equation_text_writes_three_figures_and_r_squared():
    assert equation_text(linear_fit(ANSCOMBE_I)) == \
        "//y// = 0.500//x// + 3.00, //R//^{2} = 0.667"


def test_equation_text_uses_a_true_minus_sign_for_negative_terms():
    falling = linear_fit([(x, 11.9 - 0.775 * x) for x in range(12)])
    assert equation_text(falling) == "//y// = " + MINUS + "0.775//x// + 11.9, //R//^{2} = 1.00"
    below = linear_fit([(x, 1.04 * x - 0.0516) for x in range(11)])
    text = equation_text(below)
    assert text == "//y// = 1.04//x// " + MINUS + " 0.0516, //R//^{2} = 1.00"
    assert "-" not in text


def test_figure_keeps_three_significant_figures():
    assert figure(0.5) == "0.500"
    assert figure(3.00009) == "3.00"
    assert figure(12.34) == "12.3"
    assert figure(-0.0004) == MINUS + "0.000400"
    assert figure(0.0) == "0.00"
    assert figure(-0.0) == "0.00"


def test_equation_template_is_filled_from_the_fit():
    fit = linear_fit(ANSCOMBE_I)
    assert equation_from("slope {slope:.2f}, R^{{2}} = {r2:.2f}, n = {n}", fit) == \
        "slope 0.50, R^{2} = 0.67, n = 11"
    with pytest.raises(DiagramError):
        equation_from("{nope}", fit)


def test_log_x_equation_is_written_in_log10_units():
    pts = [(10 ** (k / 5), 2 * k / 5 + 1) for k in range(1, 16)]
    fit = linear_fit([(math.log10(x), y) for x, y in pts])
    assert equation_text(fit, log_x=True) == \
        "//y// = 2.00 log_{10}(//x//) + 1.00, //R//^{2} = 1.00"


# -- the equation on a plot ----------------------------------------------------------

def _anscombe_panel(*data):
    p = inklet.panel(60, 45, x=(2, 20), y=(2, 14))
    for points in data:
        p.regression(points, equation=True)
    return p.axis("bottom").axis("left")


def test_equation_is_written_on_the_plot_and_lint_clean():
    node = _anscombe_panel(ANSCOMBE_I).build()
    assert lint(node) == []
    assert _notes(node, "regression")[0]["equation"] == \
        "//y// = 0.500//x// + 3.00, //R//^{2} = 0.667"
    (placed,) = _notes(node, "regression_equation")
    assert placed == {"count": 1, "unresolved": []}
    svg = inklet.to_svg(node)
    assert "0.500" in svg and "3.00" in svg and "0.667" in svg


def test_equation_is_placed_at_build_time_clear_of_the_marks():
    # The line and points are drawn after the call that asks for the equation,
    # so only a placement at build time can see them.
    p = inklet.panel(60, 45, x=(2, 20), y=(2, 14))
    p.regression(ANSCOMBE_I, equation=True)
    p.scatter([(4, 4), (14, 13), (4, 13), (14, 4)], color="#c1121f")
    node = p.axis("bottom").axis("left").build()
    assert lint(node) == []
    assert _notes(node, "regression_equation")[0]["unresolved"] == []


def test_a_template_string_replaces_the_default_text():
    p = inklet.panel(60, 45, x=(2, 20), y=(2, 14))
    p.regression(ANSCOMBE_I, equation="slope {slope:.1f}, R^{{2}} = {r2:.2f}")
    node = p.build()
    assert _notes(node, "regression")[0]["equation"] == "slope 0.5, R^{2} = 0.67"
    assert lint(node) == []


def test_the_equation_needs_a_linear_fit():
    p = inklet.panel(50, 36, x=(0, 26), y=(-20, 125))
    with pytest.raises(DiagramError):
        p.regression([(1, 1), (2, 4), (3, 9)], method="lowess", equation=True)


def test_a_log_x_panel_writes_the_equation_in_log_units():
    pts = [(10 ** (k / 5), 2 * k / 5 + 1) for k in range(1, 16)]
    p = inklet.panel(40, 30, x=inklet.plot.log((1, 1000)), y=(0, 8))
    p.regression(pts, equation=True).axis("bottom").axis("left")
    node = p.build()
    text = _notes(node, "regression")[0]["equation"]
    assert text == "//y// = 2.00 log_{10}(//x//) + 1.00, //R//^{2} = 1.00"
    # The label clears the line's edge by about 1.9mm, but lint's CROWDING
    # measures the bounding box of the diagonal band, whose far corner reaches
    # the label: an info-level near miss, not an overlap.
    findings = lint(node)
    assert [d for d in findings if d.severity in ("error", "warning")] == []
    assert not [d for d in findings if d.code == "OVERLAP"]


def test_the_equation_keeps_clear_of_a_wide_confidence_band():
    # The band's bounding box is most of the plot here; the equation must
    # clear the band's edges, not its box, and still find a place.
    rng = random.Random(3)
    pts = [(x, 2 + 0.6 * x + rng.gauss(0, 2.5)) for x in (rng.uniform(0, 10) for _ in range(14))]
    p = inklet.panel(60, 45, x=(0, 10), y=(-2, 16))
    p.scatter(pts).regression(pts, equation=True).axis("bottom").axis("left")
    node = p.build()
    assert lint(node) == []
    assert _notes(node, "regression_equation")[0]["unresolved"] == []


def test_two_equations_stack_without_touching():
    left = [(x, 1.0 * x + 1) for x in range(2, 12)]
    right = [(x, 9.0 - 0.5 * x) for x in range(2, 12)]
    node = _anscombe_panel(left, right).build()
    assert lint(node) == []
    unresolved = [note["unresolved"] for note in _notes(node, "regression_equation")]
    assert unresolved == [[], []]


def test_an_equation_with_no_clear_spot_is_reported_by_lint():
    # A field of marks on every spot of the plot leaves no clear place for the
    # text; it is drawn anyway and lint says so rather than hiding it.
    grid = [(a / 2, b / 2) for a in range(0, 41) for b in range(0, 41)]
    p = inklet.panel(40, 40, x=(0, 20), y=(0, 20))
    p.regression(grid, equation=True, scatter=True).axis("bottom").axis("left")
    node = p.build()
    codes = [d.code for d in lint(node)]
    assert "LABEL_UNPLACED" in codes
    (placed,) = _notes(node, "regression_equation")
    assert placed["unresolved"]


# -- quick charts ------------------------------------------------------------------------

GROUPED = {
    'x': [1, 2, 3, 4, 5, 6, 7, 8, 1, 2, 3, 4, 5, 6, 7, 8],
    'y': [2.1, 4.0, 6.2, 8.1, 9.9, 12.2, 13.9, 16.1,
          9.0, 7.6, 6.9, 5.8, 5.1, 4.2, 2.9, 2.2],
    'g': ['a'] * 8 + ['b'] * 8,
}


def test_quick_regression_keeps_a_fit_per_group_before_compiling():
    chart = i.regression(GROUPED, x='x', y='y', color='g', equation=True)
    assert set(chart.fits) == {'a', 'b'}
    fit_a = linear_fit(list(zip(GROUPED['x'][:8], GROUPED['y'][:8])))
    assert chart.fits['a'].slope == pytest.approx(fit_a.slope, rel=1e-12)
    assert chart.fits['a'].p == pytest.approx(fit_a.p, rel=1e-9)
    assert chart.fits['b'].slope < 0
    assert isinstance(chart.fits['b'], LinearFit)


def test_quick_regression_equations_are_drawn_clear_of_the_data():
    chart = i.regression(GROUPED, x='x', y='y', color='g', equation=True)
    figure_ = chart.compile()
    assert [d for d in figure_.lint() if d.severity in ('error', 'warning')] == []
    svg = figure_.to_svg(text='names')
    assert figure(chart.fits['a'].slope) in svg
    assert figure(chart.fits['b'].slope).lstrip(MINUS) in svg


def test_quick_fits_are_keyed_by_group_or_by_name_when_ungrouped():
    one = {'x': GROUPED['x'][:8], 'y': GROUPED['y'][:8]}
    assert set(i.regression(one, x='x', y='y').fits) == {None}
    assert set(i.regression(one, x='x', y='y', name='trial').fits) == {'trial'}
    # A name shared by the groups does not merge their fits into one entry.
    shared = i.regression(GROUPED, x='x', y='y', color='g', name='trial')
    assert set(shared.fits) == {'a', 'b'}


def test_quick_fits_follow_a_log_x_axis():
    data = {'x': [10 ** (k / 5) for k in range(1, 16)],
            'y': [2 * k / 5 + 1 for k in range(1, 16)]}
    chart = i.regression(data, x='x', y='y', xscale='log')
    assert chart.fits[None].slope == pytest.approx(2.0)
    assert chart.fits[None].intercept == pytest.approx(1.0)


def test_quick_lowess_keeps_no_linear_fit_and_refuses_an_equation():
    chart = i.regression(GROUPED, x='x', y='y', color='g', method='lowess')
    assert chart.fits == {}
    with pytest.raises(DiagramError):
        i.regression(GROUPED, x='x', y='y', color='g', method='lowess', equation=True)
