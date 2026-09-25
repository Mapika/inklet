"""plot.kaplan_meier, Panel.kaplan_meier and Panel.at_risk."""

from __future__ import annotations

import math
import random

import pytest

import inklet
from inklet import use_theme
from inklet.core import DiagramError, resolve
from inklet.diagnostics import lint
from inklet.draw.coords import as_drawn
from inklet.draw.shapes import MARK_LINE_KIND
from inklet.plot import SurvivalEstimate, kaplan_meier, panel, tick_values
from inklet.plot.survival import format_pvalue


@pytest.fixture(autouse=True)
def _theme():
    use_theme("nature")


# Freireich et al. (1963) 6-MP arm, weeks in remission; 0 marks a censored
# subject. The textbook example of Kaplan-Meier (Kleinbaum & Klein, ch. 2).
MP = [6, 6, 6, 7, 10, 13, 16, 22, 23, 6, 9, 10, 11, 17, 19, 20, 25, 32, 32, 34, 35]
MP_EVENTS = [1] * 9 + [0] * 12
PLACEBO = [1, 1, 2, 2, 3, 4, 4, 5, 5, 8, 8, 8, 8, 11, 11, 12, 12, 15, 17, 22, 23]

# R: summary(survfit(Surv(time, status) ~ 1, conf.type = "log-log")).
TEXTBOOK = [
    # time, n.risk, n.event, survival, std.err, lower 95%, upper 95%
    (6, 21, 3, 0.857, 0.0764, 0.620, 0.952),
    (7, 17, 1, 0.807, 0.0869, 0.563, 0.923),
    (10, 15, 1, 0.753, 0.0963, 0.503, 0.889),
    (13, 12, 1, 0.690, 0.1068, 0.432, 0.849),
    (16, 11, 1, 0.627, 0.1141, 0.368, 0.805),
    (22, 7, 1, 0.538, 0.1282, 0.268, 0.747),
    (23, 6, 1, 0.448, 0.1346, 0.188, 0.680),
]


def test_estimate_matches_the_textbook_table() -> None:
    fit = kaplan_meier(MP, MP_EVENTS)
    assert fit.times[0] == 0 and fit.survival[0] == 1 and fit.at_risk[0] == 21
    rows = list(zip(fit.times, fit.at_risk, fit.events, fit.survival,
                    [math.sqrt(v) for v in fit.variance], fit.lower, fit.upper))[1:]
    assert len(rows) == len(TEXTBOOK)
    for got, want in zip(rows, TEXTBOOK):
        assert got[:3] == want[:3]
        for g, w, places in zip(got[3:], want[3:], (3, 4, 3, 3)):
            assert round(g, places) == pytest.approx(w, abs=1e-9)
    assert fit.median == 23
    assert fit.censored == (6, 9, 10, 11, 17, 19, 20, 25, 32, 32, 34, 35)
    assert fit.band == "log-log" and fit.confidence == 0.95


def test_all_events_reach_zero_with_an_undefined_band() -> None:
    fit = kaplan_meier(PLACEBO)
    assert fit.median == 8
    assert fit.survival[-1] == 0
    assert math.isnan(fit.variance[-1]) and math.isnan(fit.lower[-1])
    assert fit.censored == ()
    # 21 subjects, two events at t=1: 19/21.
    assert fit.survival[1] == pytest.approx(19 / 21)


def test_linear_band_is_greenwood_clipped_and_none_band_is_none() -> None:
    fit = kaplan_meier(MP, MP_EVENTS, band="linear", confidence=0.9)
    z = 1.6448536269514722
    for s, v, lo, hi in zip(fit.survival, fit.variance, fit.lower, fit.upper):
        assert lo == pytest.approx(max(0.0, s - z * math.sqrt(v)))
        assert hi == pytest.approx(min(1.0, s + z * math.sqrt(v)))
    bare = kaplan_meier(MP, MP_EVENTS, band=None)
    assert bare.lower is None and bare.upper is None


def test_censoring_at_an_event_time_counts_as_at_risk() -> None:
    # Two subjects at t=5: one event, one censored. Both are at risk at 5.
    fit = kaplan_meier([5, 5, 8], [1, 0, 1])
    assert fit.at_risk[1] == 3 and fit.survival[1] == pytest.approx(2 / 3)
    assert fit.at_risk[2] == 1 and fit.survival[2] == 0
    assert fit.at(4.9) == 1 and fit.at(5) == pytest.approx(2 / 3)
    assert fit.at_risk_at(0) == 3 and fit.at_risk_at(5) == 3
    assert fit.at_risk_at(6) == 1 and fit.at_risk_at(9) == 0


def test_events_at_time_zero_drop_the_start_and_missing_values_are_skipped() -> None:
    fit = kaplan_meier([0, 0, 3, 4, None, float("nan")], [1, 0, 1, 1, 1, 0])
    assert fit.skipped == (4, 5)
    assert fit.times[0] == 0 and fit.survival[0] == pytest.approx(3 / 4)
    assert len(fit.durations) == 4


def test_matches_scipy_on_random_censored_data_with_ties() -> None:
    stats = pytest.importorskip("scipy.stats")
    if not hasattr(stats, "CensoredData"):
        pytest.skip("scipy too old for CensoredData")
    rng = random.Random(7)
    times = [float(rng.randint(1, 30)) for _ in range(80)]
    flags = [rng.random() < 0.7 for _ in times]
    data = stats.CensoredData(uncensored=[t for t, f in zip(times, flags) if f],
                              right=[t for t, f in zip(times, flags) if not f])
    sf = stats.ecdf(data).sf
    for method, band in (("log-log", "log-log"), ("linear", "linear")):
        fit = kaplan_meier(times, flags, band=band)
        ci = sf.confidence_interval(method=method)
        for q, p, lo, hi in zip(sf.quantiles, sf.probabilities,
                                ci.low.probabilities, ci.high.probabilities):
            assert fit.at(q) == pytest.approx(p, abs=1e-12)
            k = max(i for i, t in enumerate(fit.times) if t <= q)
            if not math.isnan(lo) and fit.survival[k] > 0:
                assert fit.lower[k] == pytest.approx(lo, abs=1e-9)
                assert fit.upper[k] == pytest.approx(hi, abs=1e-9)


def test_estimator_errors() -> None:
    with pytest.raises(DiagramError):
        kaplan_meier([1, 2], [1])
    with pytest.raises(DiagramError):
        kaplan_meier([-1, 2])
    with pytest.raises(DiagramError):
        kaplan_meier([1, 2], band="log")
    with pytest.raises(DiagramError):
        kaplan_meier([1, 2], confidence=1.0)
    with pytest.raises(DiagramError):
        kaplan_meier([None])


def test_pvalue_text() -> None:
    assert format_pvalue(0.0004) == "//P// < 0.001"
    assert format_pvalue(0.0123) == "//P// = 0.012"
    assert format_pvalue(0.00456) == "//P// = 0.0046"
    assert format_pvalue(0.43) == "//P// = 0.43"
    assert format_pvalue(0.003) == "//P// = 0.003"
    assert format_pvalue(0.05) == "//P// = 0.05"
    assert format_pvalue("P = n.s.") == "P = n.s."
    with pytest.raises(DiagramError):
        format_pvalue(1.5)


def _km() -> inklet.plot.Panel:
    p = panel(60, 40, x=(0, 36), y=(0, 1))
    p.kaplan_meier({"Placebo": (PLACEBO, None), "6-MP": (MP, MP_EVENTS)},
                   color=["#262626", "#24698c"], pvalue=0.00004)
    p.axes(x="Time / weeks", y="Remission")
    return p


def test_curves_bands_censor_ticks_and_legend() -> None:
    p = _km()
    note = p._content[-1].notes.get("kaplan_meier") or next(
        n.notes["kaplan_meier"] for n in p._content if "kaplan_meier" in n.notes)
    assert note["groups"] == ["Placebo", "6-MP"]
    assert note["medians"] == [8, 23]
    assert note["subjects"] == [21, 21]
    ticks = [x for x in resolve(as_drawn(p.build())).values()
             if x.diagram.kind == MARK_LINE_KIND and x.bbox.width < 1e-6
             and 0 < x.bbox.height < 2]
    # One tick per distinct censoring time of the 6-MP arm.
    assert len(ticks) == len(set(MP[9:]))
    assert [k.name for k in p.keys] == ["Placebo", "6-MP"]
    assert all(k.forms == frozenset({"area", "line"}) for k in p.keys)
    svg = inklet.to_svg(p.build())
    assert "0.001" in svg
    plain = panel(60, 40, x=(0, 36), y=(0, 1))
    plain.kaplan_meier((MP, MP_EVENTS), band=None, censors=False)
    assert plain.keys == ()
    assert len(plain._content) == 1


def test_at_risk_table_columns_sit_under_the_ticks() -> None:
    p = _km()
    before = p.build().bbox
    p.at_risk()
    table = p._over[-1]
    note = table.notes["at_risk"]
    ticks = tick_values(p.x, 5)
    assert note["times"] == ticks
    assert note["groups"] == ["Placebo", "6-MP"]
    fit = kaplan_meier(MP, MP_EVENTS)
    assert note["counts"][1] == [fit.at_risk_at(t) for t in ticks]
    assert note["counts"][0][0] == 21
    # The table is below all the furniture drawn before it.
    assert table.bbox.y0 > p.area.y1
    built = p.build()
    assert built.bbox.height > before.height
    below = p.area.y1 + 8
    numbers = [x for x in resolve(as_drawn(built)).values()
               if x.diagram.kind == "label" and x.diagram.prim is not None
               and x.bbox.center.y > below]
    rows = sorted({round(x.bbox.center.y, 3) for x in numbers})
    assert len(rows) == 3                     # the title and two groups
    for row in rows[1:]:
        centres = sorted(x.bbox.center.x for x in numbers
                         if abs(x.bbox.center.y - row) < 1e-3)
        # The name, right of nothing, then one number under each tick.
        assert centres[1:] == pytest.approx([p.x.map(t) for t in ticks], abs=1e-6)
        assert centres[0] < p.area.x0
    assert lint(built) == []


def test_at_risk_and_kaplan_meier_errors() -> None:
    with pytest.raises(DiagramError, match="kaplan_meier"):
        panel(40, 30, x=(0, 10), y=(0, 1)).at_risk()
    with pytest.raises(DiagramError):
        panel(40, 30, x=["a", "b"], y=(0, 1)).kaplan_meier(([1, 2], None))
    with pytest.raises(DiagramError):
        panel(40, 30, x=(0, 10), y=(0, 1)).kaplan_meier(([1, 2], None, None))


def test_estimates_can_be_passed_in_and_documents_build() -> None:
    fit = kaplan_meier(MP, MP_EVENTS)
    assert isinstance(fit, SurvivalEstimate)
    p = panel(40, 30, x=(0, 36), y=(0, 1))
    p.kaplan_meier({"6-MP": fit}).axes(x="t", y="S").at_risk(title=None)
    assert inklet.to_pdf(p.build())[:4] == b"%PDF"
    spec = inklet.plot_spec(x=(0, 36), y=(0, 1), height=30)
    spec.kaplan_meier({"Placebo": (PLACEBO, None)})
    spec.axes(x="t", y="S")
    spec.at_risk()
    doc = inklet.document(width=80)
    doc.add("km", spec)
    figure = doc.compile()
    assert "<path" in figure.to_svg()
    # The spec replays axes after the marks; the table must still go under
    # the axis, not over its tick labels.
    spec = inklet.plot_spec(height=32, x=(0, 36), y=(0, 1))
    spec.kaplan_meier({"Placebo": (PLACEBO, None), "6-MP": (MP, MP_EVENTS)})
    spec.axes(x="Time / weeks", y="Remission", x_options={"ticks": [0, 12, 24, 36]})
    spec.at_risk(ticks=[0, 12, 24, 36])
    doc = inklet.preset("scientific.cell").document(columns=12)
    doc.add("km", spec, row=0, column=0, colspan=5)
    assert [d for d in doc.compile().lint() if d.severity == "error"] == []
