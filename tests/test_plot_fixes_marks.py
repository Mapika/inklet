"""Regressions from the matplotlib comparison (examples/compare/ISSUES.md).

#11 translucent confidence bands, #6 the at-risk table against lint's
clearance, #8 key markers at the scatter's own size.
"""

from __future__ import annotations

import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import resolve
from inklet.diagnostics import lint
from inklet.draw.coords import active_theme, as_drawn
from inklet.plot import panel
from inklet.plot.key import SWATCH_OF_TYPE
from inklet.plot.series import swatch_for
from inklet.themes.color import mix, parse_color


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _band_nodes(p):
    return [n for n in resolve(as_drawn(p.build())).values()
            if n.style.fill not in (None, "none") and n.diagram.prim is not None
            and getattr(n.diagram.prim, "filled", False)]


# -- #11: bands ---------------------------------------------------------------


def test_a_default_band_is_the_series_colour_see_through() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.band([0, 1, 2], [2, 3, 2], [6, 8, 6], color="#0055aa", name="a")
    [band] = _band_nodes(p)
    assert band.style.fill == "#0055aa"
    assert band.style.fill_opacity == pytest.approx(0.22)
    # Over paper it paints exactly the tint the band used to be.
    paper = parse_color(active_theme().paper)
    ink = parse_color("#0055aa")
    seen = [c * 0.22 + q * 0.78 for c, q in zip(ink, paper)]
    tint = parse_color(mix("#0055aa", active_theme().paper, 0.78))
    assert seen == pytest.approx(tint, abs=1)      # 0..255 channels
    # The key keeps the opaque tint, not a solid block of the colour.
    assert p.keys[0].fill == mix("#0055aa", active_theme().paper, 0.78)


def test_overlapping_bands_both_show() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.band([0, 1, 2], [1, 2, 3], [5, 6, 7], name="a")
    p.band([0, 1, 2], [3, 2, 1], [7, 6, 5], name="b")
    bands = _band_nodes(p)
    assert len(bands) == 2
    assert all(b.style.fill_opacity is not None and b.style.fill_opacity < 1
               for b in bands)
    assert bands[0].style.fill != bands[1].style.fill


def test_an_explicit_band_fill_is_painted_as_given() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.band([0, 1, 2], [2, 3, 2], [6, 8, 6], color="#0055aa", fill="#ffcc00",
           name="a")
    [band] = _band_nodes(p)
    assert band.style.fill == "#ffcc00"
    assert band.style.fill_opacity in (None, 1, 1.0)
    assert p.keys[0].fill == "#ffcc00"


def test_line_err_and_kaplan_meier_bands_are_translucent() -> None:
    p = panel(40, 30, x=(0, 2), y=(0, 10))
    p.line([(0, 5), (1, 6), (2, 5.5)], err=1.0, name="a")
    assert [b.style.fill_opacity for b in _band_nodes(p)] == [pytest.approx(0.22)]
    km = panel(60, 40, x=(0, 30), y=(0, 1))
    km.kaplan_meier({"A": ([3, 6, 9, 12, 20, 25], [1, 1, 0, 1, 1, 0]),
                     "B": ([5, 8, 14, 18, 22, 28], [1, 0, 1, 1, 0, 1])})
    shaded = [b for b in _band_nodes(km) if b.style.fill_opacity is not None
              and b.style.fill_opacity < 1]
    assert len(shaded) == 2


# -- #6: at-risk table --------------------------------------------------------


def test_a_default_at_risk_table_lints_clean() -> None:
    rng = random.Random(4)
    arms = {}
    for name, scale in (("Standard care", 18), ("Drug A", 26),
                        ("Drug A + B", 40)):
        times = [min(60.0, rng.expovariate(1 / scale)) for _ in range(80)]
        events = [1 if t < 60 and rng.random() < 0.8 else 0 for t in times]
        arms[name] = (times, events)
    p = panel(80, 50, x=(0, 60), y=(0, 1))
    p.kaplan_meier(arms)
    p.axes(x="Time / months", y="Overall survival")
    p.at_risk()
    crowded = [d for d in lint(p.build()) if d.code == "CROWDING"]
    assert crowded == []


def test_at_risk_rows_keep_the_theme_gap_unless_asked() -> None:
    def rows(**options):
        p = panel(60, 40, x=(0, 30), y=(0, 1))
        p.kaplan_meier({"A": ([3, 6, 9, 12], [1, 1, 0, 1]),
                        "B": ([5, 8, 14, 18], [1, 0, 1, 1])})
        p.axes(x="t", y="S").at_risk(**options)
        return p._over[-1].bbox.height

    assert rows() - rows(row_gap=0.5) == pytest.approx(
        2 * (active_theme().gap("xs") - 0.5))      # title-row, row-row


# -- #8: key markers ------------------------------------------------------------


def _swatch_width(p) -> float:
    size = SWATCH_OF_TYPE * active_theme().font_size_small
    return swatch_for(p.keys[0], size).bbox.width


def test_key_marker_matches_one_scatter_size() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.scatter([(0.2, 0.2), (0.6, 0.7)], size=1.2, name="a")
    assert _swatch_width(p) == pytest.approx(1.2)


def test_key_marker_size_is_kept_within_the_row() -> None:
    size = SWATCH_OF_TYPE * active_theme().font_size_small
    big = panel(40, 30, x=(0, 1), y=(0, 1))
    big.scatter([(0.5, 0.5)], size=6.0, name="a")
    assert _swatch_width(big) == pytest.approx(size)
    tiny = panel(40, 30, x=(0, 1), y=(0, 1))
    tiny.scatter([(0.5, 0.5)], size=0.2, name="a")
    assert _swatch_width(tiny) == pytest.approx(size / 3)


def test_per_point_sizes_keep_the_default_key_marker() -> None:
    size = SWATCH_OF_TYPE * active_theme().font_size_small
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.scatter([(0.2, 0.2), (0.6, 0.7)], size=[0.5, 3.0], name="a")
    assert _swatch_width(p) == pytest.approx(size * 0.9)
    plain = panel(40, 30, x=(0, 1), y=(0, 1))
    plain.scatter([(0.2, 0.2)], name="a")
    assert _swatch_width(plain) == pytest.approx(size * 0.9)


def test_a_line_with_markers_keys_the_marker_size() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.line([(0, 0), (1, 1)], name="a")
    p.scatter([(0, 0), (1, 1)], size=1.0, name="a")
    [entry] = p.keys
    assert entry.marker_size == pytest.approx(1.0)
    assert {"line", "marker"} <= entry.forms
