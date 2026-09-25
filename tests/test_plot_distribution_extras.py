"""Histogram variants, boxen, strip, sina, 100% bars, pair and joint plots."""

import math
import random
import re

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError
from inklet.diagnostics import lint
from inklet.plot import (cumulate, histogram, letter_values, percent_of_totals)


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


def sample(n=200, seed=1, mu=0.0, sd=1.0):
    rng = random.Random(seed)
    return [rng.gauss(mu, sd) for _ in range(n)]


# -- histograms ------------------------------------------------------------------

def test_cumulate_counts_and_densities():
    edges, counts = histogram([0.5, 1.5, 1.6, 2.5], [0, 1, 2, 3])
    assert cumulate(edges, counts, False) == (1, 3, 4)
    edges, dens = histogram([0.5, 1.5, 1.6, 2.5], [0, 1, 2, 3], density=True)
    assert cumulate(edges, dens, True) == pytest.approx((0.25, 0.75, 1.0))


def test_legacy_hist_is_unchanged_by_the_new_options():
    def build(**kw):
        return inklet.panel(40, 30, x=(-4, 4), y=(0, 60)).hist(sample(), 12, **kw).build()
    assert _svg(build()) == _svg(build(histtype=None, cumulative=False))
    assert _svg(build()) == _svg(build(histtype="bar"))


def test_hist_groups_share_edges_and_name_the_legend():
    groups = {"control": sample(300, 1, 4, 1), "treated": sample(200, 2, 6, 1.4)}
    p = inklet.panel(40, 30, x=(0, 12), y=(0, 90))
    p.hist(groups, 20).axis("bottom").axis("left").legend()
    node = p.build()
    # overlaid groups touch by design; only information-level crowding
    assert [d for d in lint(node) if d.severity != "info"] == []
    note = _notes(node, "hist")[0]
    assert note["groups"] == ["control", "treated"]
    assert note["histtype"] == "stepfilled"
    assert [k.name for k in p.keys] == ["control", "treated"]


@pytest.mark.parametrize("histtype", ["step", "stepfilled"])
def test_hist_outline_types(histtype):
    p = inklet.panel(40, 30, x=(-4, 4), y=(0, 60))
    p.hist(sample(), 16, histtype=histtype).axis("bottom").axis("left")
    assert lint(p.build()) == []
    with pytest.raises(DiagramError):
        inklet.panel(10, 10, x=(0, 1), y=(0, 1)).hist([0.5], histtype="bars")


def test_cumulative_density_hist_ends_at_one():
    values = sample(500)
    p = inklet.panel(40, 30, x=(-4, 4), y=(0, 1))
    p.hist(values, 25, cumulative=True, density=True, histtype="step")
    node = p.build()
    assert _notes(node, "hist")[0]["cumulative"] is True
    edges, dens = histogram(values, 25, density=True)
    assert cumulate(edges, dens, True)[-1] == pytest.approx(1.0)
    assert lint(p.axis("bottom").axis("left").build()) == []


# -- 100% bars ----------------------------------------------------------------------

def test_percent_of_totals():
    out = percent_of_totals([[1, 0, 2], [3, 0, 2]])
    assert out == ((25.0, 0.0, 50.0), (75.0, 0.0, 50.0))
    with pytest.raises(DiagramError):
        percent_of_totals([[1, -1], [1, 1]])


def test_normalized_bars_stack_to_100_with_percent_labels():
    at = ["S1", "S2", "S3"]
    heights = [[12, 30, 5], [20, 10, 15], [8, 12, 30]]
    p = inklet.panel(40, 30, x=at, y=(0, 100))
    p.bars(at, heights, normalize=True, labels=True, name=["a", "b", "c"])
    p.axis("bottom").axis("left")
    node = p.build()
    assert lint(node) == []
    svg = inklet.to_svg(node)
    assert "30%" in svg and "50%" in svg


def test_normalized_bars_match_explicit_stacked_percentages():
    at = ["x", "y"]
    heights = [[1, 3], [3, 1]]
    a = inklet.panel(30, 30, x=at, y=(0, 100)).bars(at, heights, normalize=True).build()
    b = inklet.panel(30, 30, x=at, y=(0, 100)).bars(
        at, [[25, 75], [75, 25]], stacked=True).build()
    assert _svg(a) == _svg(b)


# -- letter values and boxen ---------------------------------------------------------

def test_letter_values_depths_and_quantiles():
    values = list(range(1, 101))
    lv = letter_values(values)
    assert len(lv.boxes) == math.floor(math.log2(100)) - 3
    assert lv.median == 50.5
    assert lv.boxes[0] == pytest.approx((25.75, 75.25))
    assert lv.boxes[1] == pytest.approx((1 + 99 * 0.125, 1 + 99 * 0.875))
    low, high = lv.boxes[-1]
    assert lv.outliers == tuple(v for v in values if v < low or v > high)
    assert len(letter_values(values, depth=2).boxes) == 2
    assert len(letter_values(list(range(10000)), depth="trustworthy").boxes) == 12
    with pytest.raises(DiagramError):
        letter_values(values, depth="deep")


def test_letter_values_match_numpy_quantiles():
    np = pytest.importorskip("numpy")
    values = sample(5000, seed=11)
    lv = letter_values(values)
    for k, (lo, hi) in enumerate(lv.boxes):
        q = 2.0 ** -(k + 2)
        assert lo == pytest.approx(np.quantile(values, q))
        assert hi == pytest.approx(np.quantile(values, 1 - q))


def test_boxen_panel_is_lint_clean_and_deterministic():
    groups = {"A": sample(2000, 1), "B": sample(2000, 2, 1, 1.5)}

    def build():
        p = inklet.panel(40, 36, x=list(groups), y=(-6, 8))
        return p.boxen(groups).axis("bottom").axis("left").build()
    node = build()
    assert lint(node) == []
    assert _notes(node, "boxen")[0]["boxes"] == [7, 7]
    assert _svg(node) == _svg(build())


def test_boxen_horizontal():
    groups = {"A": sample(500, 1), "B": sample(500, 2, 1)}
    p = inklet.panel(40, 30, y=list(groups), x=(-5, 6))
    p.boxen(groups, orient="h", outliers=False).axis("bottom").axis("left")
    assert lint(p.build()) == []


# -- strip and sina -------------------------------------------------------------------

def test_strip_is_seeded_and_stays_in_its_slot():
    groups = {"A": sample(60, 1), "B": sample(60, 2, 1)}

    def build(seed=0):
        p = inklet.panel(40, 36, x=list(groups), y=(-4, 5))
        return p.strip(groups, size=0.8, seed=seed).axis("bottom").axis("left")
    p = build()
    node = p.build()
    assert lint(node) == []
    assert _svg(node) == _svg(build().build())
    assert _svg(node) != _svg(build(seed=1).build())
    assert _notes(node, "strip")[0]["drawn"] == [60, 60]


def test_strip_without_jitter_is_a_column():
    p = inklet.panel(30, 30, x=["A"], y=(-4, 4)).strip({"A": sample(20)}, jitter=0)
    node = [n for n in _walk(p.build()) if n.kind == "strip"][0]
    xs = {round(c.transform.e, 9) for c in node.children}
    assert len(xs) == 1
    with pytest.raises(DiagramError):
        inklet.panel(30, 30, x=["A"], y=(-4, 4)).strip({"A": [1, 2]}, jitter=2)


def test_sina_spread_follows_the_density():
    groups = {"A": sample(400, 3)}
    p = inklet.panel(30, 40, x=["A"], y=(-4, 4)).sina(groups, size=0.5)
    node = p.build()
    assert lint(p.axis("bottom").axis("left").build()) == []
    sina = [n for n in _walk(node) if n.kind == "sina"][0]
    centre = p.x.map("A")
    offsets = [(abs(c.transform.e - centre), c.transform.f) for c in sina.children]
    middle = [o for o, y in offsets if abs(y - p.y.map(0)) < 3]
    tails = [o for o, y in offsets if abs(y - p.y.map(0)) > 12]
    assert max(middle) > 2 * max(tails)
    assert _notes(node, "sina")[0]["bandwidth"][0] > 0


# -- pair and joint plots --------------------------------------------------------------

def iris_like(seed=4):
    rng = random.Random(seed)
    groups = ["a"] * 40 + ["b"] * 40
    data = {"u": [], "v": [], "w": []}
    for g in groups:
        shift = 0 if g == "a" else 2
        data["u"].append(rng.gauss(5 + shift, 0.5))
        data["v"].append(rng.gauss(3, 0.4))
        data["w"].append(rng.gauss(1.5 + 2 * shift, 0.5))
    return data, groups


def test_pairplot_grid_is_aligned_and_lint_clean():
    data, groups = iris_like()
    grid = inklet.pairplot(data, groups=groups, cell=22)
    assert lint(grid) == []
    panels = [n for n in _walk(grid) if n.kind == "panel"]
    assert len(panels) == 9
    assert _svg(grid) == _svg(inklet.pairplot(data, groups=groups, cell=22))


@pytest.mark.parametrize("kinds", [dict(lower="kde2d", upper=None, corner=True, diag="kde"),
                                   dict(lower="hexbin", upper="regression", diag="hist"),
                                   dict(lower="hist2d", upper="scatter", diag=None)])
def test_pairplot_kinds(kinds):
    data, _ = iris_like()
    assert lint(inklet.pairplot(data, cell=20, **kinds)) == []


def test_pairplot_log_variable_and_errors():
    data, _ = iris_like()
    data["w"] = [math.exp(v) for v in data["w"]]
    assert lint(inklet.pairplot(data, log=["w"], cell=20)) == []
    with pytest.raises(DiagramError):
        inklet.pairplot(data, lower="violin")
    with pytest.raises(DiagramError):
        inklet.pairplot(data, vars=["u", "nope"])
    with pytest.raises(DiagramError):
        inklet.pairplot({"u": [1, 2], "v": [1]})


def test_jointplot_kinds_and_groups():
    rng = random.Random(6)
    pts = [(x, 0.5 * x + rng.gauss(0, 1)) for x in (rng.gauss(0, 1) for _ in range(500))]
    for kind, marginal in (("scatter", "hist"), ("hexbin", "kde"), ("kde2d", "kde"),
                           ("regression", "hist")):
        g = inklet.jointplot(pts, kind=kind, marginal=marginal, x_label="x", y_label="y")
        assert lint(g) == [], kind
    groups = ["p" if k % 2 else "q" for k in range(500)]
    g = inklet.jointplot(pts, groups=groups, marginal="kde")
    assert lint(g) == []
    assert _svg(g) == _svg(inklet.jointplot(pts, groups=groups, marginal="kde"))
    with pytest.raises(DiagramError):
        inklet.jointplot(pts, ratio=1)
