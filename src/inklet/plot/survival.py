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
`band="linear"` gives `S +- z * sqrt(Var)`, clipped to [0, 1]. Where the
estimate reaches 0 the variance and the band are undefined (NaN) and the
band is not drawn.

`Panel.kaplan_meier` draws step curves, censor ticks and the bands;
`Panel.at_risk` hangs the number-at-risk table under the x axis. There is no
significance test here: pass a p-value computed elsewhere to `pvalue=`.
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
           "format_pvalue", "at_risk_table", "AT_RISK_KIND"]

#: Accepted values of `kaplan_meier(band=)`.
SURVIVAL_BANDS = ("log-log", "linear", None)

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
    `"log-log"` (default), `"linear"` or None. See the module docstring for
    the formulas.
    """
    if band not in SURVIVAL_BANDS:
        raise DiagramError(
            f'kaplan_meier band is "log-log", "linear" or None, not {band!r}')
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


def censor_ticks(panel, estimate: SurvivalEstimate, size: float, **style) -> list[Diagram]:
    """A short vertical tick on the curve at each censoring time."""
    out = []
    for t in dict.fromkeys(estimate.censored):
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
    between = theme.gap("xs") * 0.5 if row_gap is None else mm(row_gap)
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


