"""Kaplan-Meier survival curves, their confidence bands and the at-risk table.

`kaplan_meier` does the arithmetic and draws nothing. From each subject's
duration and whether the event was observed (True) or the subject was
censored (False) it computes the product-limit estimate

    S(t) = prod over event times t_i <= t of (1 - d_i / n_i),

where `d_i` is the number of events at `t_i` and `n_i` the number of
subjects at risk just before it (those whose duration is at least `t_i`).
A subject censored at an event time is counted at risk there: censoring is
taken to happen just after the events at the same time.

The variance is Greenwood's,

    Var S(t) = S(t)^2 * sum d_i / (n_i (n_i - d_i)).

The default confidence band is the log-log ("exponential Greenwood") one:
the interval is built for log(-log S), which keeps it inside (0, 1), and
gives `S ** exp(+-z * se)` with `se = sqrt(sum d/(n(n-d))) / |log S|`.
`band="log"` -- R's `survfit` default, `conf.type = "log"` -- builds it for
log S instead: `S * exp(+-z * sqrt(sum d/(n(n-d))))`, the upper edge clipped
to 1. `band="linear"` gives `S +- z * sqrt(Var)`, clipped to [0, 1]. Where
the estimate reaches 0 the variance and the band are undefined (NaN) and the
band is not drawn.

`logrank` is the Mantel-Cox log-rank test between two or more groups: at each
distinct event time t, with `n_j` at risk and `d_j` events in group j (and
`n`, `d` overall), group j expects `E_j = d n_j / n` events, and the
hypergeometric covariance is

    V_jk = d (n - d) / (n - 1) * n_j / n * (delta_jk - n_k / n).

The statistic `(O - E)' V^-1 (O - E)`, over all groups but the last, is
chi-square on k - 1 degrees of freedom; its p-value comes from the
regularized upper incomplete gamma function (`erfc` for one degree of
freedom). This is what R's `survdiff` reports.

`Panel.kaplan_meier` draws step curves, censor ticks and the bands;
`Panel.at_risk` hangs the number-at-risk table under the x axis.
`kaplan_meier(pvalue="logrank")` writes the log-rank p-value on the plot.
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, mm
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND
from .axis import text_node, tick_values

__all__ = ["kaplan_meier", "SurvivalEstimate", "SURVIVAL_BANDS",
           "format_pvalue", "at_risk_table", "AT_RISK_KIND", "logrank",
           "LogRank", "chi2_sf"]

#: Accepted values of `kaplan_meier(band=)`.
SURVIVAL_BANDS = ("log-log", "log", "linear", None)

AT_RISK_KIND = "at-risk"



@dataclass(frozen=True)
class SurvivalEstimate:
    """A Kaplan-Meier estimate.

    `times` starts at 0 and then lists each distinct event time. At each,
    `survival` is the estimate just after it, `at_risk` the number at risk
    just before it, `events` the number of events, `variance` Greenwood's
    variance of the estimate, and `lower` and `upper` the confidence band
    (None when `band` is None). `censored` lists the censoring times, one
    per censored subject, in order, and `durations` every duration used.
    `skipped` are the input indices left out for a missing value.
    """
    times: tuple[float, ...]
    survival: tuple[float, ...]
    at_risk: tuple[int, ...]
    events: tuple[int, ...]
    variance: tuple[float, ...]
    lower: tuple[float, ...] | None
    upper: tuple[float, ...] | None
    censored: tuple[float, ...]
    durations: tuple[float, ...]
    confidence: float
    band: str | None
    skipped: tuple[int, ...] = ()

    def at(self, t: float) -> float:
        """The estimate at time `t` (right-continuous: after any drop at `t`)."""
        k = bisect.bisect_right(self.times, t) - 1
        return self.survival[max(k, 0)]

    def at_risk_at(self, t: float) -> int:
        """How many subjects are at risk at time `t`: durations of at least `t`."""
        return len(self.durations) - bisect.bisect_left(self.durations, t)

    @property
    def median(self) -> float | None:
        """The first time the estimate is at or below 0.5, or None if it never is."""
        for time, value in zip(self.times, self.survival):
            if value <= 0.5 + 1e-12:
                return time
        return None

    @property
    def end(self) -> float:
        """The last observed time, event or censored."""
        return self.durations[-1]


def _missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def kaplan_meier(durations: Sequence[float], events: Sequence | None = None, *,
                 confidence: float = 0.95,
                 band: str | None = "log-log") -> SurvivalEstimate:
    """The Kaplan-Meier estimate of survival, without drawing it.

    `durations` is each subject's follow-up time and `events` whether the
    event was observed (truthy) or the subject was censored (falsy); leave
    `events` out when every event was observed. Subjects with a missing
    duration or event flag (None or NaN) are skipped and listed in
    `skipped`. `confidence` is the band's coverage and `band` its kind:
    `"log-log"` (default), `"log"` (R's default), `"linear"` or None. See
    the module docstring for the formulas.
    """
    if band not in SURVIVAL_BANDS:
        raise DiagramError(
            f'kaplan_meier band is "log-log", "log", "linear" or None, not {band!r}')
    if not 0 < confidence < 1:
        raise DiagramError(
            f"kaplan_meier confidence must be in (0, 1), got {confidence!r}")
    durations = list(durations)
    flags = [True] * len(durations) if events is None else list(events)
    if len(flags) != len(durations):
        raise DiagramError(
            f"kaplan_meier needs one event flag per duration, got {len(durations)} "
            f"durations and {len(flags)} flags")
    kept: list[tuple[float, bool]] = []
    skipped: list[int] = []
    for index, (t, e) in enumerate(zip(durations, flags)):
        if _missing(t) or _missing(e):
            skipped.append(index)
            continue
        t = float(t)
        if not math.isfinite(t) or t < 0:
            raise DiagramError(
                f"kaplan_meier duration {t!r} at index {index} is not a time of 0 or more")
        kept.append((t, bool(e)))
    if not kept:
        raise DiagramError("kaplan_meier has no subjects to estimate from")
    kept.sort()
    order = tuple(t for t, _ in kept)
    event_count: dict[float, int] = {}
    for t, e in kept:
        if e:
            event_count[t] = event_count.get(t, 0) + 1
    censored = tuple(t for t, e in kept if not e)
    z = NormalDist().inv_cdf(0.5 + confidence / 2)

    times, survival, at_risk, deaths, variance = [0.0], [1.0], [len(kept)], [0], [0.0]
    lower: list[float] = [1.0]
    upper: list[float] = [1.0]
    s, greenwood = 1.0, 0.0
    for t in sorted(event_count):
        d = event_count[t]
        n = len(order) - bisect.bisect_left(order, t)
        s *= 1.0 - d / n
        greenwood = greenwood + d / (n * (n - d)) if n > d else math.inf
        if t == 0.0:
            # Events at time 0 drop the curve at its start; keep one entry.
            times.pop(), survival.pop(), at_risk.pop(), deaths.pop(), variance.pop()
            lower.pop(), upper.pop()
        times.append(t)
        survival.append(s)
        at_risk.append(n)
        deaths.append(d)
        if s > 0:
            variance.append(s * s * greenwood)
            lo, hi = _interval(s, greenwood, z, band)
        else:
            variance.append(math.nan)
            lo = hi = math.nan
        lower.append(lo)
        upper.append(hi)
    return SurvivalEstimate(
        times=tuple(times), survival=tuple(survival), at_risk=tuple(at_risk),
        events=tuple(deaths), variance=tuple(variance),
        lower=None if band is None else tuple(lower),
        upper=None if band is None else tuple(upper),
        censored=censored, durations=order, confidence=confidence, band=band,
        skipped=tuple(skipped))


def _interval(s: float, greenwood: float, z: float, band: str | None) -> tuple[float, float]:
    if band is None:
        return s, s
    if band == "linear":
        spread = z * s * math.sqrt(greenwood)
        return max(0.0, s - spread), min(1.0, s + spread)
    if band == "log":
        spread = math.exp(z * math.sqrt(greenwood))
        return s / spread, min(1.0, s * spread)
    if s >= 1.0:
        return 1.0, 1.0
    log_s = math.log(s)
    se = math.sqrt(greenwood) / abs(log_s)
    return s ** math.exp(z * se), s ** math.exp(-z * se)


def format_pvalue(p: float | str) -> str:
    """`p` as it is set on a figure: `P = 0.012`, `P < 0.001`, with an
    italic P. A string is returned as given."""
    if isinstance(p, str):
        return p
    p = float(p)
    if not 0 <= p <= 1:
        raise DiagramError(f"a p-value is in [0, 1], got {p!r}")
    if p < 0.001:
        return "//P// < 0.001"
    if p >= 0.1:
        return f"//P// = {p:.2f}"
    # At most two significant figures, written out as a decimal.
    digits = 1 - math.floor(math.log10(p))
    return f"//P// = {p:.{digits}f}".rstrip("0")


def _groups(data) -> list[tuple[str | None, Sequence, Sequence | None]]:
    """`(name, durations, events)` per group."""
    if isinstance(data, SurvivalEstimate):
        return [(None, data, None)]
    if isinstance(data, Mapping):
        out = []
        for name, value in data.items():
            if isinstance(value, SurvivalEstimate):
                out.append((str(name), value, None))
            elif isinstance(value, Mapping):
                out.append((str(name), value["durations"], value.get("events")))
            else:
                parts = list(value)
                if len(parts) != 2:
                    raise DiagramError(
                        f"kaplan_meier group {name!r} is (durations, events), "
                        "a mapping with those keys, or a SurvivalEstimate")
                out.append((str(name), parts[0], parts[1]))
        if not out:
            raise DiagramError("kaplan_meier was given no groups")
        return out
    parts = list(data)
    if len(parts) != 2:
        raise DiagramError(
            "kaplan_meier takes a mapping of group name to (durations, events), "
            "or one (durations, events) pair")
    return [(None, parts[0], parts[1])]


def estimates(data, *, confidence: float, band: str | None) -> list[tuple[str | None, SurvivalEstimate]]:
    """Each group's name and estimate."""
    out = []
    for name, durations, events in _groups(data):
        if isinstance(durations, SurvivalEstimate):
            out.append((name, durations))
        else:
            out.append((name, kaplan_meier(durations, events, confidence=confidence,
                                           band=band)))
    return out


@dataclass(frozen=True)
class LogRank:
    """The result of `logrank`: the chi-square `statistic` on `df` degrees
    of freedom, its `p`-value, and per group (in `groups` order) the
    `observed` and `expected` numbers of events."""
    statistic: float
    df: int
    p: float
    groups: tuple[str | None, ...]
    observed: tuple[float, ...]
    expected: tuple[float, ...]


def logrank(data) -> LogRank:
    """The log-rank (Mantel-Cox) test that survival differs between groups.

    `data` takes every form `Panel.kaplan_meier` takes -- a mapping of group
    name to `(durations, events)`, or to a `SurvivalEstimate` -- with at
    least two groups. Two groups give chi-square on 1 degree of freedom, k
    groups on k - 1; the numbers match R's `survdiff(Surv(time, status) ~
    group)`. See the module docstring for the formula.

        result = inklet.plot.logrank({"Male": (t_m, e_m), "Female": (t_f, e_f)})
        result.statistic, result.p        # 10.33, 0.0013 for the NCCTG lung data
    """
    return logrank_of(estimates(data, confidence=0.95, band=None))


def logrank_of(groups: Sequence[tuple[str | None, SurvivalEstimate]]) -> LogRank:
    """`logrank` of `(name, estimate)` pairs already computed."""
    groups = list(groups)
    if len(groups) < 2:
        raise DiagramError("a log-rank test needs at least two groups")
    events = [{t: d for t, d in zip(e.times, e.events) if d > 0} for _, e in groups]
    times = sorted(set().union(*events))
    k = len(groups)
    observed = [float(sum(found.values())) for found in events]
    expected = [0.0] * k
    cov = [[0.0] * k for _ in range(k)]
    for t in times:
        risk = [e.at_risk_at(t) for _, e in groups]
        n = sum(risk)
        d = sum(found.get(t, 0) for found in events)
        if n <= 0:
            continue
        for j in range(k):
            expected[j] += d * risk[j] / n
        if n > 1:
            scale = d * (n - d) / (n - 1)
            for j in range(k):
                for m in range(k):
                    share = (1.0 if j == m else 0.0) - risk[m] / n
                    cov[j][m] += scale * risk[j] / n * share
    diff = [o - e for o, e in zip(observed, expected)]
    statistic = _quadratic_form([row[:k - 1] for row in cov[:k - 1]], diff[:k - 1])
    return LogRank(statistic=statistic, df=k - 1, p=chi2_sf(statistic, k - 1),
                   groups=tuple(name for name, _ in groups),
                   observed=tuple(observed), expected=tuple(expected))


def _quadratic_form(matrix: list[list[float]], vector: list[float]) -> float:
    """`v' M^-1 v`, by Gaussian elimination with partial pivoting."""
    size = len(vector)
    rows = [list(row) + [value] for row, value in zip(matrix, vector)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(rows[r][col]))
        if abs(rows[pivot][col]) < 1e-12:
            raise DiagramError(
                "the log-rank variance is singular: a group has no subjects "
                "at risk at any event time")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        for r in range(col + 1, size):
            factor = rows[r][col] / rows[col][col]
            for c in range(col, size + 1):
                rows[r][c] -= factor * rows[col][c]
    solution = [0.0] * size
    for r in reversed(range(size)):
        total = rows[r][size] - sum(rows[r][c] * solution[c] for c in range(r + 1, size))
        solution[r] = total / rows[r][r]
    return max(0.0, sum(v * x for v, x in zip(vector, solution)))


def chi2_sf(x: float, df: int) -> float:
    """P(X > x) for X chi-square on `df` degrees of freedom."""
    if df < 1:
        raise DiagramError(f"chi-square needs at least 1 degree of freedom, got {df!r}")
    if x <= 0:
        return 1.0
    if df == 1:
        return math.erfc(math.sqrt(x / 2))
    return _gamma_q(df / 2, x / 2)


def _gamma_q(a: float, x: float) -> float:
    """The regularized upper incomplete gamma function Q(a, x)."""
    log_front = a * math.log(x) - x - math.lgamma(a)
    if x < a + 1:
        # Series for P(a, x), then Q = 1 - P.
        term = total = 1.0 / a
        ap = a
        for _ in range(1000):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return max(0.0, 1.0 - total * math.exp(log_front))
    # Continued fraction for Q(a, x), by the modified Lentz method.
    tiny = 1e-300
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-15:
            break
    return math.exp(log_front) * h


def curve_points(estimate: SurvivalEstimate, end: float | None = None) -> list[tuple[float, float]]:
    """The corners of the step curve, from (0, 1) to the last observed time."""
    last = estimate.end if end is None else end
    points = [(estimate.times[0], estimate.survival[0])]
    for t, s in zip(estimate.times[1:], estimate.survival[1:]):
        points.append((t, s))
    if last > points[-1][0]:
        points.append((last, points[-1][1]))
    return points


def band_edges(estimate: SurvivalEstimate) -> tuple[list, list, list]:
    """`(x, lower, upper)` tracing the band as steps, stopping where it is NaN."""
    xs: list[float] = []
    lo: list[float] = []
    hi: list[float] = []
    times = list(estimate.times) + [estimate.end]
    for k in range(len(estimate.times)):
        a, b = times[k], times[k + 1]
        low, high = estimate.lower[k], estimate.upper[k]
        if math.isnan(low) or math.isnan(high):
            break
        if b <= a:
            continue
        xs.extend((a, b))
        lo.extend((low, low))
        hi.extend((high, high))
    return xs, lo, hi


def censor_ticks(panel, estimate: SurvivalEstimate, size: float, *,
                 within: tuple[float, float] | None = None,
                 **style) -> list[Diagram]:
    """A short vertical tick on the curve at each censoring time.

    `within=(lo, hi)` keeps only the times in that closed range -- the x
    domain of a clipping panel, so a subject followed past the axis's end
    leaves no empty clipped node behind.
    """
    out = []
    for t in dict.fromkeys(estimate.censored):
        if within is not None and not within[0] <= t <= within[1]:
            continue
        at = panel.point(t, estimate.at(t))
        out.append(polyline(((at.x, at.y - size / 2), (at.x, at.y + size / 2)),
                            kind=MARK_LINE_KIND, **style))
    return out


def at_risk_table(panel, groups: Sequence[tuple[str | None, SurvivalEstimate, str]], *,
                  ticks: Sequence | None = None, count: int = 5,
                  title: str | None = "Number at risk",
                  font_size: float | str | None = None,
                  row_gap: float | str | None = None, markup: bool = True,
                  readable=None) -> tuple[Diagram, dict]:
    """The number-at-risk table, in panel coordinates, its top at y=0.

    One column per x tick value (`tick_values` of the panel's x scale, as
    the axis draws them, or `ticks=`), centred on the tick; one row per
    group, the group's name right-aligned against the plot area's left edge
    and every entry in the group's colour. The caller moves it below the
    furniture.
    """
    theme = active_theme()
    size = theme.font_size_small if font_size is None else mm(font_size)
    values = tuple(tick_values(panel.x, count, horizontal=True) if ticks is None else ticks)
    area = panel.area
    values = tuple(v for v in values
                   if area.x0 - 1e-6 <= panel.x.map(v) <= area.x1 + 1e-6)
    if not values:
        raise DiagramError("at_risk has no x tick inside the plot area to put a column under")
    # By default the line boxes keep the clearance lint checks text against
    # (or the theme's small gap, if larger), so a descender in one name
    # never crowds the capitals of the next.
    from .point_labels import lint_clearance
    between = (max(theme.gap("xs"), lint_clearance()) if row_gap is None
               else mm(row_gap))
    rows = []
    counts: list[list[int]] = []
    for name, estimate, color in groups:
        ink = color if readable is None else readable(color)
        row = [estimate.at_risk_at(v) for v in values]
        counts.append(row)
        cells = [text_node(str(n), size, "label", features={"tnum": True},
                           text_fill=ink) for n in row]
        cells = [cell.translated(panel.x.map(v) - cell.bbox.center.x, 0.0)
                 for v, cell in zip(values, cells)]
        label = (text_node(name, size, "label", markup=markup, text_fill=ink)
                 if name else None)
        rows.append((cells, label))
    # The names end a gap short of the plot's left edge or of the first
    # column's widest entry, whichever is further left.
    first = min(min(cell.bbox.x0 for cell in cells) for cells, _ in rows)
    right = min(area.x0, first) - theme.gap("s")
    parts: list[Diagram] = []
    y = 0.0
    if title is not None:
        heading = text_node(title, size, "label", markup=markup)
        labels = [label for _, label in rows if label is not None]
        left = (min(right - label.bbox.width for label in labels) if labels
                else first)
        box = heading.bbox
        parts.append(heading.translated(left - box.x0, y - box.y0))
        y += box.height + between
    for cells, label in rows:
        height = max(cell.bbox.height for cell in cells)
        for cell in cells:
            parts.append(cell.translated(0.0, y + height / 2 - cell.bbox.center.y))
        if label is not None:
            box = label.bbox
            parts.append(label.translated(right - box.x1,
                                          y + height / 2 - box.center.y))
        y += height + between
    node = draw_place(parts, origin=(0, 0), kind=AT_RISK_KIND)
    note = {"times": values, "counts": counts,
            "groups": [name for name, _, _ in groups]}
    node.notes["at_risk"] = note
    return node, note


def pvalue_text(p, size: float) -> Diagram:
    return text_node(format_pvalue(p), size, "label")


