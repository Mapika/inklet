"""Regressions from the published-figure recreations, round 2: marks.

ISSUES-medicine-econ #1 (censor ticks past an explicit x domain) and #6
(band="log", the log-rank test), ISSUES-physics #3 (dash= and paint keywords
checked at the call).
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.draw.coords import as_drawn
from inklet.plot import kaplan_meier, logrank, panel
from inklet.plot.paint import DASHES, dash_pattern
from inklet.plot.survival import chi2_sf

LUNG = Path(__file__).resolve().parents[1] / "examples" / "published" / "ncctg_lung" / "data" / "lung.csv"


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


def _compile(spec, width=90):
    doc = inklet.document(width=width)
    doc.add("a", spec)
    return doc.compile()


# -- censor ticks past the domain --------------------------------------------


def test_censor_ticks_past_a_clipped_x_domain_leave_no_empty_node() -> None:
    spec = inklet.plot_spec(x=(0, 10), y=(0, 1), clip=True)
    spec.kaplan_meier({"A": ([2, 4, 6, 12], [1, 1, 0, 0])})
    figure = _compile(spec)
    assert "EMPTY_DIAGRAM" not in figure.report()
    # The tick at t = 6 is still drawn; the one at t = 12 is not.
    p = panel(40, 30, x=(0, 10), y=(0, 1), clip=True)
    p.kaplan_meier({"A": ([2, 4, 6, 12], [1, 1, 0, 0])})
    built = resolve(as_drawn(p.build()))
    empty = [q for q in built.values()
             if q.diagram.prim is None and not q.diagram.children]
    assert not empty


def test_the_chart_api_repro_is_clean() -> None:
    chart = inklet.chart(xlim=(0, 10), ylim=(0, 1))
    chart.kaplan_meier({"A": ([2, 4, 6, 12], [1, 1, 0, 0])})
    assert "EMPTY_DIAGRAM" not in chart.document().compile().report()


def test_censor_ticks_are_kept_when_the_panel_does_not_clip() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 1))
    p.kaplan_meier({"A": ([2, 4, 6, 12], [1, 1, 0, 0])})
    ticks = [q for q in resolve(as_drawn(p.build())).values()
             if q.diagram.kind == "mark-line" and q.bbox.height < 2.5
             and q.bbox.width < 0.5]
    assert len(ticks) == 2


# -- band="log" ----------------------------------------------------------------


def test_the_log_band_is_s_times_exp_of_z_se() -> None:
    durations = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    events = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1]
    fit = kaplan_meier(durations, events, band="log")
    z = 1.959963984540054
    greenwood = 0.0
    for k in range(1, len(fit.times)):
        n, d = fit.at_risk[k], fit.events[k]
        if n == d:
            assert math.isnan(fit.lower[k])
            break
        greenwood += d / (n * (n - d))
        s = fit.survival[k]
        assert fit.lower[k] == pytest.approx(s * math.exp(-z * math.sqrt(greenwood)))
        assert fit.upper[k] == pytest.approx(min(1.0, s * math.exp(z * math.sqrt(greenwood))))
    assert all(hi <= 1.0 for hi in fit.upper if not math.isnan(hi))


def test_the_log_band_draws() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 1))
    p.kaplan_meier({"a": ([1, 2, 3, 5, 8], [1, 1, 0, 1, 0])}, band="log")
    note = [n.notes["kaplan_meier"] for n in p.build().walk() if "kaplan_meier" in n.notes]
    assert note[0]["band"] == "log"


# -- log-rank ----------------------------------------------------------------


def _lung():
    with LUNG.open() as handle:
        rows = list(csv.DictReader(handle))
    time = [float(r["time"]) for r in rows]
    dead = [r["status"] == "2" for r in rows]
    return rows, time, dead


def test_logrank_matches_survdiff_on_the_ncctg_lung_data() -> None:
    rows, time, dead = _lung()
    male = [r["sex"] == "1" for r in rows]
    arms = {"Male": ([t for t, m in zip(time, male) if m], [e for e, m in zip(dead, male) if m]),
            "Female": ([t for t, m in zip(time, male) if not m],
                       [e for e, m in zip(dead, male) if not m])}
    result = logrank(arms)
    # R: survdiff(Surv(time, status) ~ sex, data = lung)
    assert result.df == 1
    assert result.statistic == pytest.approx(10.33, abs=0.005)
    assert result.p == pytest.approx(0.0013, abs=0.00005)
    assert result.observed == (112.0, 53.0)
    assert result.expected == pytest.approx((91.6, 73.4), abs=0.05)


def test_logrank_with_k_groups_matches_survdiff() -> None:
    rows, time, dead = _lung()
    groups = {}
    for r, t, e in zip(rows, time, dead):
        if r["ph.ecog"] in ("", "NA"):
            continue
        groups.setdefault(r["ph.ecog"], ([], []))
        groups[r["ph.ecog"]][0].append(t)
        groups[r["ph.ecog"]][1].append(e)
    result = logrank(dict(sorted(groups.items())))
    # R: survdiff(Surv(time, status) ~ ph.ecog, data = lung): Chisq = 22 on 3 df, p = 7e-05
    assert result.df == 3
    assert result.statistic == pytest.approx(21.96, abs=0.01)
    assert result.p == pytest.approx(6.64e-05, rel=0.01)


def test_chi2_survival_function() -> None:
    assert chi2_sf(3.841458820694124, 1) == pytest.approx(0.05)
    assert chi2_sf(7.814727903251178, 3) == pytest.approx(0.05)
    assert chi2_sf(2.0, 4) == pytest.approx(0.7357588823428847)
    assert chi2_sf(0.5, 3) == pytest.approx(0.9188914116546758)
    assert chi2_sf(60.0, 2) == pytest.approx(math.exp(-30.0))
    assert chi2_sf(0.0, 2) == 1.0


def test_logrank_needs_two_groups() -> None:
    with pytest.raises(DiagramError, match="two groups"):
        logrank({"a": ([1, 2, 3], [1, 1, 1])})


def test_pvalue_logrank_writes_the_test_on_the_plot() -> None:
    p = panel(40, 30, x=(0, 10), y=(0, 1))
    data = {"a": ([1, 2, 3, 4, 5], [1, 1, 1, 0, 1]), "b": ([4, 6, 7, 8, 9], [0, 1, 1, 1, 0])}
    p.kaplan_meier(data, pvalue="logrank")
    built = p.build()
    texts = " ".join(q.diagram.prim.text for q in resolve(as_drawn(built)).values()
                     if hasattr(q.diagram.prim, "text"))
    assert "Log-rank" in texts
    note = [n.notes["kaplan_meier"] for n in built.walk() if "kaplan_meier" in n.notes][0]
    assert note["logrank"]["p"] == pytest.approx(logrank(data).p)
    assert note["logrank"]["df"] == 1


# -- dash= and the paint keywords -------------------------------------------------


def _dashes(p) -> list:
    return [q.style.stroke_dash for q in resolve(as_drawn(p.build())).values()
            if q.diagram.prim is not None and q.style.stroke_dash is not None]


@pytest.mark.parametrize("method, args", [
    ("line", ([(0, 0), (1, 1)],)),
    ("step", ([(0, 0), (1, 1)],)),
    ("hline", (0.5,)),
    ("vline", (0.5,)),
    ("errorbars", ([(0.5, 0.5)],)),
    ("ecdf", ([0.1, 0.4, 0.6],)),
])
def test_dash_names_a_pattern_on_every_stroked_mark(method, args) -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    extra = {"yerr": 0.1} if method == "errorbars" else {}
    getattr(p, method)(*args, dash="dashed", **extra)
    assert tuple(DASHES["dashed"]) in [tuple(d) for d in _dashes(p)]


def test_dash_on_filled_outlines_and_survival_curves() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    p.fill([(0, 0.2), (1, 0.4)], stroke="#000000", dash="dotted")
    p.fill_between([0, 1], 0.1, 0.3, stroke="#000000", dash=(1.0, 0.5))
    seen = [tuple(d) for d in _dashes(p)]
    assert DASHES["dotted"] in seen and (1.0, 0.5) in seen
    q = panel(40, 30, x=(0, 10), y=(0, 1))
    q.kaplan_meier({"a": ([1, 2, 3], [1, 1, 1])}, dash="dashdot")
    assert DASHES["dashdot"] in [tuple(d) for d in _dashes(q)]


def test_dash_is_recorded_in_the_key_and_compiles_in_a_recipe() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1)).line([(0, 0), (1, 1)], dash="dashed", name="a")
    assert p.keys[0].dash == DASHES["dashed"]
    spec = inklet.plot_spec().line([(0, 0), (1, 1)], dash="dashed")
    svg = _compile(spec).to_svg()
    assert "stroke-dasharray" in svg
    solid = panel(40, 30, x=(0, 1), y=(0, 1)).line([(0, 0), (1, 1)], dash="solid")
    assert _dashes(solid) == []
    assert dash_pattern("dashed") == (1.6, 0.8)
    with pytest.raises(ValueError, match="unknown dash"):
        dash_pattern("wiggly")
    with pytest.raises(ValueError):
        dash_pattern((0, 0))


def test_an_unknown_paint_keyword_fails_at_the_call() -> None:
    spec = inklet.plot_spec()
    with pytest.raises(TypeError, match=r"linestyle= \(did you mean dash=\?\)"):
        spec.line([(0, 0), (1, 1)], linestyle="--")
    with pytest.raises(TypeError, match=r"stroke_dahs= \(did you mean stroke_dash=\?\)"):
        spec.hline(0.5, stroke_dahs=(1, 1))
    with pytest.raises(ValueError, match="unknown dash"):
        spec.line([(0, 0), (1, 1)], dash="wiggly")
    with pytest.raises(TypeError, match="both dash= and stroke_dash="):
        spec.line([(0, 0), (1, 1)], dash="dashed", stroke_dash=(1, 1))
    p = panel(40, 30, x=(0, 1), y=(0, 1))
    with pytest.raises(TypeError, match="alpha= .did you mean opacity="):
        p.scatter([(0.5, 0.5)], alpha=0.5)
    # Nothing was recorded by the failed calls.
    assert spec._steps == []


def test_known_pass_through_keywords_are_still_accepted() -> None:
    p = panel(40, 30, x=(0, 1), y=(0, 1), clip=True)
    p.line([(0, 0), (1, 1)], clip=False, color="#ff0000", kind="mark-line",
           stroke_linecap="round", opacity=0.5)
    p.scatter([(0.5, 0.5)], anchor="center", fill_opacity=0.5)
    p.rect(0.1, 0.1, 0.2, 0.2, fill_rule="evenodd")
    p.build()
